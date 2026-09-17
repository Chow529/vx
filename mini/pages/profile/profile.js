// pages/profile/profile.js - 我的页面
const api = require('../../utils/api')

Page({
  data: {
    userInfo: null,
    stats: null,
    loading: true
  },

  onShow() {
    this.loadProfile()
    this.loadStats()
  },

  loadProfile() {
    const app = getApp()
    const userInfo = app.globalData.userInfo
    if (userInfo) {
      this.setData({ userInfo })
    }
  },

  loadStats() {
    api.get('/questions/stats/overview').then(stats => {
      const techList = Object.entries(stats.tech_distribution || {}).map(([name, count]) => ({ name, count }))
      const masteryList = [
        { name: '未掌握', count: (stats.mastery_distribution || {})['0'] || 0 },
        { name: '学习中', count: (stats.mastery_distribution || {})['1'] || 0 },
        { name: '已掌握', count: (stats.mastery_distribution || {})['2'] || 0 }
      ]
      this.setData({
        stats: { ...stats, techList, masteryList },
        loading: false
      })
    }).catch(() => this.setData({ loading: false }))
  },

  goToMyQuestions() {
    wx.switchTab({ url: '/pages/my-questions/my-questions' })
  },

  goToPublicQuestions() {
    wx.navigateTo({ url: '/pages/public-questions/public-questions' })
  },

  goToQuiz() {
    wx.navigateTo({ url: '/pages/quiz/quiz' })
  },

  goToArchived() {
    // 跳转到题库页的归档模式 (通过全局变量传递状态)
    const pages = getCurrentPages()
    this.setData({ goToArchived: true })
    wx.switchTab({ url: '/pages/my-questions/my-questions' })
  }
})
