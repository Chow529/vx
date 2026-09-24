// pages/question-detail/question-detail.js - 题目详情页
const api = require('../../utils/api')

Page({
  data: {
    questionId: 0,
    question: null,
    showAnswer: false,
    loading: true,
    // 编辑弹窗
    editing: false,
    editForm: { title: '', content: '', answer: '', tech_stack: '', difficulty: 1 },
    difficultyOptions: ['简单', '中等', '困难']
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

  // 弹窗内阻止冒泡用的空函数
  noop() {},

  // 设置掌握程度（分段控件）
  setMastery(e) {
    const m = Number(e.currentTarget.dataset.value)
    if (m === this.data.question.mastery) return
    api.post(`/questions/${this.data.questionId}/mastery?mastery=${m}`).then(() => {
      this.loadQuestion()
      wx.showToast({ title: ['未掌握', '学习中', '已掌握'][m], icon: 'success' })
    })
  },

  // ─── 发布 / 撤销 ───
  publishToCommunity() {
    const q = this.data.question
    if (!q || q.is_published) return
    wx.showModal({
      title: '发布到社区',
      content: '确定要将此题目发布到社区圈吗？',
      success: (res) => {
        if (res.confirm) {
          api.post(`/questions/${this.data.questionId}/publish`, {}).then(() => {
            wx.showToast({ title: '发布成功', icon: 'success' })
            this.loadQuestion()
          }).catch(err => {
            wx.showToast({ title: (err && err.message) || '发布失败', icon: 'none' })
          })
        }
      }
    })
  },

  withdrawFromCommunity() {
    const q = this.data.question
    if (!q || !q.is_published) return
    wx.showModal({
      title: '撤销发布',
      content: '撤销后社区中的对应帖子将被删除，确定吗？',
      success: (res) => {
        if (res.confirm) {
          api.post(`/questions/${this.data.questionId}/withdraw`, {}).then(() => {
            wx.showToast({ title: '已撤销', icon: 'success' })
            this.loadQuestion()
          }).catch(err => {
            wx.showToast({ title: (err && err.message) || '撤销失败', icon: 'none' })
          })
        }
      }
    })
  },

  // ─── 编辑 ───
  openEdit() {
    const q = this.data.question
    this.setData({
      editing: true,
      editForm: {
        title: q.title,
        content: q.content,
        answer: q.answer,
        tech_stack: q.tech_stack,
        difficulty: q.difficulty
      }
    })
  },

  closeEdit() {
    this.setData({ editing: false })
  },

  onEditInput(e) {
    const field = e.currentTarget.dataset.field
    const form = { ...this.data.editForm, [field]: e.detail.value }
    this.setData({ editForm: form })
  },

  onEditDifficulty(e) {
    const form = { ...this.data.editForm, difficulty: Number(e.detail.value) + 1 }
    this.setData({ editForm: form })
  },

  saveEdit() {
    const { title, content, answer, tech_stack, difficulty } = this.data.editForm
    if (!title.trim() || !content.trim()) {
      wx.showToast({ title: '标题和内容不能为空', icon: 'none' })
      return
    }
    api.put(`/questions/${this.data.questionId}`, {
      title: title.trim(),
      content: content.trim(),
      answer: answer.trim(),
      tech_stack: tech_stack.trim() || '其他',
      difficulty: Number(difficulty)
    }).then(() => {
      wx.showToast({ title: '已保存', icon: 'success' })
      this.setData({ editing: false })
      this.loadQuestion()
    }).catch(err => {
      wx.showToast({ title: (err && err.message) || '保存失败', icon: 'none' })
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
  }
})

function formatDate(dateStr) {
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
