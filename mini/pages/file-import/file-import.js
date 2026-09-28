// pages/file-import/file-import.js - 文件导入题库（流式解析）
const api = require('../../utils/api')

Page({
  data: {
    filePath: '',
    fileName: '',
    parsing: false,     // 是否正在流式解析
    stopped: false,     // 是否被手动停止
    total: 0,           // 后端解析出的总条数
    items: [],          // 已呈现的题目（边收边加）
    selectedIds: [],
    selectAll: true,
    submitting: false,
    // 导入配置
    techStack: '其他',
    difficulty: 1,
    techOptions: ['其他'],
    difficultyOptions: ['简单', '中等', '困难']
  },

  onLoad() {
    this.loadTechStacks()
  },

  onUnload() {
    // 离开页面时中断未完成的流式请求
    this._abortStream()
  },

  loadTechStacks() {
    api.get('/questions/tech-stacks').then(res => {
      if (res.stacks && res.stacks.length > 0) {
        this.setData({ techOptions: res.stacks })
      }
    }).catch(err => {
      console.error('加载技术栈失败:', err)
      // 降级使用默认列表
      this.setData({
        techOptions: ['Python', 'Java', 'JavaScript', '前端', '后端', 'AI 大模型', '算法', '数据库', '其他']
      })
    })
  },

  chooseFile() {
    if (this.data.parsing) {
      wx.showToast({ title: '解析中，请先停止', icon: 'none' })
      return
    }
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['.pdf', '.doc', '.docx', '.md'],
      success: (res) => {
        const file = res.tempFiles[0]
        this.setData({
          filePath: file.path,
          fileName: file.name,
          items: [],
          selectedIds: [],
          total: 0,
          stopped: false
        })
        wx.showToast({ title: '文件已选择', icon: 'success' })
      }
    })
  },

  // ─── 流式解析 ───

  parseFile() {
    if (!this.data.filePath) {
      wx.showToast({ title: '请先选择文件', icon: 'none' })
      return
    }
    // 读成 ArrayBuffer：wx.uploadFile 不支持分块接收，只能用 wx.request + enableChunked
    wx.getFileSystemManager().readFile({
      filePath: this.data.filePath,
      success: (res) => this._startStream(res.data),
      fail: () => wx.showToast({ title: '读取文件失败', icon: 'none' })
    })
  },

  _startStream(arrayBuffer) {
    const app = getApp()
    const baseUrl = (app && app.globalData && app.globalData.baseUrl) || 'http://127.0.0.1:8000/api'
    const token = (app && app.globalData && app.globalData.token) || ''

    // 重置流式状态
    this._buf = new Uint8Array(0)   // 未凑成整行的残留字节
    this._rawText = ''              // 原始响应文本（用于错误提示）
    this._aborted = false
    this.setData({
      parsing: true, stopped: false, total: 0,
      items: [], selectedIds: [], selectAll: true
    })

    this._task = wx.request({
      url: baseUrl + '/questions/upload',
      method: 'POST',
      enableChunked: true,
      data: arrayBuffer,
      header: {
        'Content-Type': 'application/octet-stream',
        'X-Filename': encodeURIComponent(this.data.fileName || 'unknown'),
        'Authorization': 'Bearer ' + token
      },
      success: (res) => {
        // 流结束（正常或异常中断）都要解除解析中状态
        this.setData({ parsing: false })
        if (res.statusCode !== 200) {
          wx.showToast({ title: this._errorDetail(res), icon: 'none', duration: 3000 })
        }
      },
      fail: (err) => {
        if (this._aborted) return  // 用户主动停止，不提示错误
        this.setData({ parsing: false })
        wx.showToast({ title: '解析失败：' + ((err && err.errMsg) || '网络错误'), icon: 'none' })
      },
      complete: () => { this._task = null }
    })

    // 每收到一块数据就尝试切出完整行并渲染
    this._task.onChunkReceived((res) => this._appendChunk(res.data))
  },

  _abortStream() {
    if (this._task) {
      this._aborted = true
      this._task.abort()
      this._task = null
    }
  },

  stopParse() {
    if (!this.data.parsing) return
    this._abortStream()
    const kept = this.data.items.length
    this.setData({ parsing: false, stopped: true })
    wx.showToast({ title: `已停止，保留 ${kept} 条`, icon: 'none' })
  },

  /** 错误详情：优先取后端 detail，否则取原始响应片段 */
  _errorDetail(res) {
    let detail = ''
    if (res.data && typeof res.data === 'object') {
      detail = res.data.detail || ''
    }
    if (!detail && this._rawText) {
      try { detail = JSON.parse(this._rawText).detail || '' } catch (e) { detail = '' }
    }
    return detail || ('解析失败 (HTTP ' + res.statusCode + ')')
  },

  /** 拼接字节流，按 \n 切出完整行（避免多字节中文被截断） */
  _appendChunk(arrayBuffer) {
    const incoming = new Uint8Array(arrayBuffer)
    const prev = this._buf || new Uint8Array(0)
    const merged = new Uint8Array(prev.length + incoming.length)
    merged.set(prev)
    merged.set(incoming, prev.length)

    let start = 0
    for (let i = 0; i < merged.length; i++) {
      if (merged[i] !== 0x0A) continue  // \n
      const line = this._decodeUtf8(merged.subarray(start, i))
      start = i + 1
      if (!line.trim()) continue
      this._rawText += line
      this._handleLine(line)
    }
    this._buf = merged.subarray(start)
  },

  _decodeUtf8(bytes) {
    if (!this._decoder && typeof TextDecoder !== 'undefined') {
      this._decoder = new TextDecoder('utf-8')
    }
    if (this._decoder) return this._decoder.decode(bytes)
    // 兜底：逐字节拼 latin1 再按 UTF-8 解
    let s = ''
    const CHUNK = 8192
    for (let i = 0; i < bytes.length; i += CHUNK) {
      s += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK))
    }
    try { return decodeURIComponent(escape(s)) } catch (e) { return s }
  },

  /** 处理一行 NDJSON 消息 */
  _handleLine(line) {
    let msg
    try { msg = JSON.parse(line) } catch (e) { return }

    if (msg.type === 'start') {
      this.setData({ total: msg.total || 0 })
      return
    }

    if (msg.type === 'item') {
      const q = msg.question || ''
      const difficulty = msg.difficulty || 1
      const item = {
        id: msg.index,
        question: q,
        answer: msg.answer || '',
        section: msg.section || '',
        tech_stack: msg.tech_stack || '其他',
        difficulty,
        difficultyLabel: ['', '简单', '中等', '困难'][difficulty],
        difficultyClass: ['', 'green', 'orange', 'red'][difficulty],
        preview: q.substring(0, 80) + (q.length > 80 ? '...' : ''),
        selected: true
      }
      // 直接推入数组，只 setData 新增的那一项，避免整表重渲染
      const items = this.data.items
      items.push(item)
      this.setData({
        ['items[' + (items.length - 1) + ']']: item,
        selectedIds: this.data.selectedIds.concat(item.id),
        selectAll: true
      })
      return
    }

    if (msg.type === 'done') {
      this.setData({ parsing: false, stopped: false })
      wx.showToast({ title: `解析完成：${msg.count} 道题`, icon: 'success' })
    }
  },

  toggleItem(e) {
    if (this.data.parsing) return  // 解析中不允许改选，避免与流式追加冲突
    const idx = e.currentTarget.dataset.index
    const items = this.data.items
    items[idx].selected = !items[idx].selected
    const selectedIds = items.filter(i => i.selected).map(i => i.id)
    this.setData({
      items,
      selectedIds,
      selectAll: selectedIds.length === items.length
    })
  },

  toggleSelectAll() {
    const selectAll = !this.data.selectAll
    const items = this.data.items.map(i => ({ ...i, selected: selectAll }))
    const selectedIds = selectAll ? items.map(i => i.id) : []
    this.setData({ items, selectedIds, selectAll })
  },

  pickTech(e) {
    this.setData({ techStack: this.data.techOptions[e.detail.value] })
  },

  pickDifficulty(e) {
    this.setData({ difficulty: Number(e.detail.value) + 1 })
  },

  importQuestions() {
    if (this.data.parsing) {
      wx.showToast({ title: '解析中，请先停止再导入', icon: 'none' })
      return
    }
    if (this.data.selectedIds.length === 0) {
      wx.showToast({ title: '请至少选择一道题目', icon: 'none' })
      return
    }

    this.setData({ submitting: true })
    // 只导入已呈现且被勾选的题目
    const selectedItems = this.data.items.filter(i => i.selected).map(item => {
      const tech = item.tech_stack || this.data.techStack
      return {
        title: item.question,
        content: item.question,
        answer: item.answer || '',
        tech_stack: tech,
        difficulty: item.difficulty || this.data.difficulty,
        // 章节信息作为标签保留，不丢弃文档结构
        tags: [tech, item.section].filter(Boolean)
      }
    })

    api.post('/questions/import', selectedItems).then(res => {
      wx.showToast({ title: `成功导入 ${res.count} 道题目`, icon: 'success' })
      this.setData({
        filePath: '',
        fileName: '',
        items: [],
        selectedIds: [],
        total: 0,
        stopped: false,
        submitting: false
      })
      setTimeout(() => {
        wx.switchTab({ url: '/pages/my-questions/my-questions' })
      }, 1000)
    }).catch(err => {
      this.setData({ submitting: false })
      wx.showToast({ title: '导入失败', icon: 'none' })
    })
  }
})
