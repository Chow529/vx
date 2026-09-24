// pages/quiz/quiz.js
const api = require('../../utils/api')

Page({
  data: {
    // 配置阶段
    step: 'config', // config / quiz / result
    count: 10,
    source: 'all', // all / my_questions
    tech_stack: '',
    difficulty: '',
    
    // 答题阶段
    questions: [],
    currentIdx: 0,
    userAnswers: [],
    score: 0,
    percent: 0
  },

  onLoad() {
    this.loadTechStacks()
  },

  loadTechStacks() {
    api.get('/questions/tech-stacks').then(res => {
      if (res.stacks && res.stacks.length > 0) {
        this.setData({ techStacks: res.stacks })
      }
    }).catch(() => {})
  },

  onCountInput(e) {
    // 输入时只更新值，不做校验
    const val = e.detail.value
    this.setData({ count: val === '' ? '' : parseInt(val) || 10 })
  },

  onCountBlur() {
    // 失焦时才校验
    let count = parseInt(this.data.count) || 10
    if (count < 10) {
      count = 10
      wx.showToast({ title: '最少 10 题', icon: 'none' })
    }
    this.setData({ count })
  },

  onSourceChange(e) {
    const sources = ['全部题库', '我的题库']
    this.setData({ source: e.detail.value === '0' ? 'all' : 'my_questions' })
  },

  onTechChange(e) {
    const val = this.data.techStacks[e.detail.value]
    this.setData({ tech_stack: val })
  },

  onDifficultyChange(e) {
    const levels = ['', '简单', '中等', '困难']
    const val = e.detail.value
    this.setData({ difficulty: val === '0' ? '' : Number(val) })
  },

  startQuiz() {
    // 前端验证
    if (this.data.count < 10) {
      wx.showToast({ title: '最少 10 题', icon: 'none' })
      return
    }

    wx.showLoading({ title: 'AI 正在出题...' })
    
    const params = {
      count: this.data.count,
      source: this.data.source
    }
    if (this.data.tech_stack) params.tech_stack = this.data.tech_stack
    if (this.data.difficulty) params.difficulty = this.data.difficulty

    api.post('/quiz/generate', params).then(res => {
      wx.hideLoading()
      
      // 如果返回的题目数量少于请求数量，提示用户
      if (res.total < this.data.count) {
        wx.showToast({
          title: `题库不足，已出 ${res.total} 题`,
          icon: 'none',
          duration: 2000
        })
      }
      
      this.setData({
        step: 'quiz',
        questions: res.questions,
        currentIdx: 0,
        userAnswers: new Array(res.questions.length).fill(null),
        score: 0
      })
    }).catch(err => {
      wx.hideLoading()
      wx.showToast({ title: '生成失败：' + (err.message || '未知错误'), icon: 'none' })
    })
  },

  selectAnswer(e) {
    const idx = this.data.currentIdx
    const answer = e.currentTarget.dataset.answer
    const userAnswers = [...this.data.userAnswers]
    userAnswers[idx] = answer
    this.setData({ userAnswers })
  },

  nextQuestion() {
    if (this.data.currentIdx < this.data.questions.length - 1) {
      this.setData({ currentIdx: this.data.currentIdx + 1 })
    } else {
      // 计算得分
      let score = 0
      this.data.questions.forEach((q, i) => {
        if (this.data.userAnswers[i] === q.correct_answer) {
          score++
        }
      })
      this.setData({
        step: 'result',
        score: score,
        total: this.data.questions.length,
        percent: Math.round(score / this.data.questions.length * 100)
      })
    }
  },

  prevQuestion() {
    if (this.data.currentIdx > 0) {
      this.setData({ currentIdx: this.data.currentIdx - 1 })
    }
  },

  restart() {
    this.setData({
      step: 'config',
      questions: [],
      currentIdx: 0,
      userAnswers: [],
      score: 0,
      percent: 0
    })
  }
})
