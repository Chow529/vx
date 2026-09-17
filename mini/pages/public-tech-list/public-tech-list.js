// pages/public-tech-list/public-tech-list.js - 技术栈题目列表页
const api = require('../../utils/api')

Page({
  data: {
    tech: '',
    questions: [],
    loading: false,
    page: 1,
    total: 0,
    showUpload: false,
    uploadForm: {
      title: '',
      content: '',
      answer: '',
      difficulty: 1
    }
  },

  onLoad(options) {
    const tech = decodeURIComponent(options.tech || '')
    wx.setNavigationBarTitle({ title: tech + ' - 公共题库' })
    this.setData({ tech })
    this.loadQuestions()
  },

  loadQuestions() {
    this.setData({ loading: true })
    api.get('/public-questions/', {
      page: this.data.page,
      size: 20,
      tech_stack: this.data.tech
    }).then(res => {
      this.setData({
        questions: this.data.page === 1 ? res.items : [...this.data.questions, ...res.items],
        total: res.total,
        loading: false
      })
    }).catch(() => this.setData({ loading: false }))
  },

  toggleUpload() {
    this.setData({ showUpload: !this.data.showUpload })
  },

  onFormInput(e) {
    const field = e.currentTarget.dataset.field
    const form = { ...this.data.uploadForm, [field]: e.detail.value }
    this.setData({ uploadForm: form })
  },

  onDifficultyChange(e) {
    const form = { ...this.data.uploadForm, difficulty: Number(e.detail.value) + 1 }
    this.setData({ uploadForm: form })
  },

  uploadQuestion() {
    const { title, content, answer, difficulty } = this.data.uploadForm
    if (!title.trim() || !content.trim()) {
      wx.showToast({ title: '请填写标题和内容', icon: 'none' })
      return
    }

    api.post('/public-questions/', {
      title: title.trim(),
      content: content.trim(),
      answer: answer.trim(),
      tech_stack: this.data.tech,
      difficulty: Number(difficulty)
    }).then(() => {
      wx.showToast({ title: '上传成功', icon: 'success' })
      this.setData({
        showUpload: false,
        uploadForm: { title: '', content: '', answer: '', difficulty: 1 },
        page: 1,
        questions: []
      })
      this.loadQuestions()
    })
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/public-question-detail/public-question-detail?id=${id}` })
  },

  onReachBottom() {
    if (this.data.questions.length < this.data.total) {
      this.setData({ page: this.data.page + 1 })
      this.loadQuestions()
    }
  }
})
