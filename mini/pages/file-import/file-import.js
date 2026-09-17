// pages/file-import/file-import.js - 文件导入题库
const api = require('../../utils/api')

Page({
  data: {
    filePath: '',
    fileName: '',
    parsing: false,
    parsed: false,
    items: [],
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
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['.pdf', '.doc', '.docx', '.md'],
      success: (res) => {
        const file = res.tempFiles[0]
        this.setData({
          filePath: file.path,
          fileName: file.name,
          parsed: false,
          items: [],
          selectedIds: []
        })
        wx.showToast({ title: '文件已选择', icon: 'success' })
      }
    })
  },

  parseFile() {
    if (!this.data.filePath) {
      wx.showToast({ title: '请先选择文件', icon: 'none' })
      return
    }

    this.setData({ parsing: true })
    api.upload('/questions/upload', this.data.filePath).then(res => {
      const items = res.items.map((item, idx) => ({
        ...item,
        id: idx,
        selected: true,
        preview: item.question.substring(0, 80) + (item.question.length > 80 ? '...' : ''),
        tech_stack: item.tech_stack || '其他',
        difficulty: item.difficulty || 1,
        difficultyLabel: ['', '简单', '中等', '困难'][item.difficulty || 1],
        difficultyClass: ['', 'green', 'orange', 'red'][item.difficulty || 1]
      }))
      this.setData({
        items,
        parsed: true,
        parsing: false,
        selectedIds: items.map(i => i.id),
        selectAll: true
      })
      wx.showToast({ title: `解析成功：${items.length} 道题目`, icon: 'success' })
    }).catch(err => {
      this.setData({ parsing: false })
      wx.showToast({ title: '解析失败：' + (err.message || '未知错误'), icon: 'none' })
    })
  },

  toggleItem(e) {
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
    if (this.data.selectedIds.length === 0) {
      wx.showToast({ title: '请至少选择一道题目', icon: 'none' })
      return
    }

    this.setData({ submitting: true })
    const selectedItems = this.data.selectedIds.map(id => this.data.items[id]).map(item => ({
      title: item.question,
      content: item.question,
      answer: item.answer || '',
      tech_stack: item.tech_stack || this.data.techStack,  // 优先使用 AI 分析的结果
      difficulty: item.difficulty || this.data.difficulty,  // 优先使用 AI 分析的结果
      tags: [item.tech_stack || this.data.techStack]
    }))

    api.post('/questions/import', selectedItems).then(res => {
      wx.showToast({ title: `成功导入 ${res.count} 道题目`, icon: 'success' })
      this.setData({
        filePath: '',
        fileName: '',
        parsed: false,
        items: [],
        selectedIds: [],
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
