// pages/question-detail/question-detail.js - 题目详情页（查看题目+答案）
const api = require('../../utils/api')

Page({
  data: {
    questionId: 0,
    question: null,
    showAnswer: false,
    loading: true
  },

  onLoad(options) {
    const questionId = Number(options.id)
    this.setData({ questionId })
    this.loadQuestion()
  },

  loadQuestion() {
    api.get(`/questions/${this.data.questionId}`).then(res => {
      this.setData({
        question: {
          ...res,
          difficultyLabel: ['', '简单', '中等', '困难'][res.difficulty],
          difficultyClass: ['', 'green', 'orange', 'red'][res.difficulty],
          masteryLabel: ['未掌握', '学习中', '已掌握'][res.mastery],
          sourceLabel: { manual: '手动录入', file_import: '文件导入', community: '社区收藏' }[res.source] || res.source,
          createdAt: formatDate(res.created_at)
        },
        loading: false
      })
    }).catch(() => this.setData({ loading: false }))
  },

  toggleAnswer() {
    this.setData({ showAnswer: !this.data.showAnswer })
  },

  cycleMastery() {
    const current = this.data.question.mastery
    const next = (current + 1) % 3
    api.post(`/questions/${this.data.questionId}/mastery?mastery=${next}`).then(() => {
      this.loadQuestion()
      wx.showToast({
        title: ['未掌握', '学习中', '已掌握'][next],
        icon: 'success'
      })
    })
  },

  deleteQuestion() {
    wx.showModal({
      title: '确认删除',
      content: '删除后无法恢复，确定删除吗？',
      success: (res) => {
        if (res.confirm) {
          api.del(`/questions/${this.data.questionId}`).then(() => {
            wx.showToast({ title: '已删除', icon: 'success' })
            setTimeout(() => wx.navigateBack(), 500)
          })
        }
      }
    })
  },

  publishToCommunity() {
    const q = this.data.question
    if (!q) return
    wx.showModal({
      title: '发布到社区',
      content: '确定要将此题目发布到社区圈吗？',
      success: (res) => {
        if (res.confirm) {
          api.post('/posts/', {
            title: q.title,
            content: q.content,
            tech_stack: q.tech_stack,
            difficulty: q.difficulty,
            tags: q.tags || [],
            also_save_to_my: false
          }).then(() => {
            wx.showToast({ title: '发布成功', icon: 'success' })
          }).catch(err => {
            wx.showToast({ title: '发布失败', icon: 'none' })
          })
        }
      }
    })
  }
})

function formatDate(dateStr) {
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
}
