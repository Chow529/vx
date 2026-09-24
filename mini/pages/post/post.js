// pages/post/post.js - 发布题目帖
const api = require('../../utils/api')

Page({
  data: {
    title: '',
    content: '',
    answer: '',
    techStack: '其他',
    difficulty: 1,
    tags: '',
    alsoSaveToMy: false,
    techOptions: ['其他'],
    difficultyOptions: ['简单', '中等', '困难'],
    submitting: false
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

  onTitleInput(e) { this.setData({ title: e.detail.value }) },
  onContentInput(e) { this.setData({ content: e.detail.value }) },
  onAnswerInput(e) { this.setData({ answer: e.detail.value }) },
  onTagsInput(e) { this.setData({ tags: e.detail.value }) },

  pickTech(e) {
    const idx = e.detail.value
    this.setData({ techStack: this.data.techOptions[idx] })
  },

  pickDifficulty(e) {
    this.setData({ difficulty: Number(e.detail.value) + 1 })
  },

  toggleSaveToMy(e) {
    this.setData({ alsoSaveToMy: e.detail.value })
  },

  submitPost() {
    const { title, content, answer, techStack, difficulty, tags, alsoSaveToMy } = this.data
    if (!title.trim()) {
      wx.showToast({ title: '请输入标题', icon: 'none' })
      return
    }
    if (!content.trim()) {
      wx.showToast({ title: '请输入内容', icon: 'none' })
      return
    }

    this.setData({ submitting: true })
    const tagList = tags ? tags.split(/[,，\s]+/).filter(Boolean) : []

    api.post('/posts/', {
      title: title.trim(),
      content: content.trim(),
      answer: answer.trim(),
      tech_stack: techStack,
      difficulty,
      tags: tagList,
      also_save_to_my: alsoSaveToMy
    }).then(() => {
      wx.showToast({ title: '发布成功', icon: 'success' })
      this.setData({
        title: '', content: '', answer: '', tags: '',
        techStack: '其他', difficulty: 1, alsoSaveToMy: false
      })
      // 跳转到社区首页
      setTimeout(() => wx.switchTab({ url: '/pages/index/index' }), 500)
    }).finally(() => this.setData({ submitting: false }))
  }
})
