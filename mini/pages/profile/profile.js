// pages/profile/profile.js - 我的页面
const api = require('../../utils/api')

Page({
  data: {
    userInfo: null,
    stats: null,
    loading: true,
    nicknameDraft: ''   // 输入框当前内容（失焦/切页时兜底保存用）
  },

  onShow() {
    this.loadProfile()
    this.loadStats()
  },

  onHide() {
    // 切 tab 时 input 不会失焦，这里兜底保存一次，避免用户改完昵称没生效
    this.saveNicknameIfChanged()
  },

  onUnload() {
    this.saveNicknameIfChanged()
  },

  loadProfile() {
    const app = getApp()
    // 若上次昵称保存还在飞行中，先等它完成再拉取，
    // 否则可能用旧数据覆盖刚保存的新昵称
    const pending = this._savePromise || Promise.resolve()
    pending.catch(() => {}).then(() => {
      // 登录可能还没完成，等登录就绪后再取用户信息
      return app.ensureLogin()
    })
      .then(() => app.refreshUserInfo())
      .then(() => this.refreshProfile())
      .catch(() => {})
  },

  /** 用最新的全局用户信息填充页面 */
  refreshProfile() {
    const app = getApp()
    const userInfo = app.globalData.userInfo
    if (userInfo) {
      this.setData({
        userInfo,
        nicknameDraft: userInfo.nickname || ''
      })
    }
  },

  /**
   * 用户选择头像后回调
   * 微信给的是临时文件路径，必须上传到服务器转存，否则过段时间就失效
   * 后端按用户 ID 命名并覆盖旧文件，同一次请求顺带把昵称也提交了
   */
  onChooseAvatar(e) {
    const tempPath = e.detail.avatarUrl
    if (!tempPath) return

    const app = getApp()
    const baseUrl = (app && app.globalData && app.globalData.baseUrl) || ''
    const nickname = this.data.nicknameDraft || (this.data.userInfo && this.data.userInfo.nickname) || ''

    wx.showLoading({ title: '上传中...' })
    wx.uploadFile({
      url: baseUrl.replace(/\/api$/, '') + '/api/auth/avatar',
      filePath: tempPath,
      name: 'file',
      // 头像与昵称一起提交，省一次请求
      formData: nickname ? { nickname } : {},
      header: {
        'Authorization': `Bearer ${app.globalData.token}`
      },
      success: (res) => {
        wx.hideLoading()
        let data = {}
        try { data = JSON.parse(res.data) } catch (err) {}
        if (res.statusCode === 200 && data.avatar_url) {
          const updated = {
            ...app.globalData.userInfo,
            avatar_url: data.avatar_url,
            nickname: data.nickname
          }
          app.globalData.userInfo = updated
          wx.setStorageSync('userInfo', updated)
          this.setData({ userInfo: updated, nicknameDraft: data.nickname || '' })
          wx.showToast({ title: '已更新', icon: 'success' })
        } else {
          wx.showToast({ title: data.detail || '头像上传失败', icon: 'none' })
        }
      },
      fail: () => {
        wx.hideLoading()
        wx.showToast({ title: '头像上传失败', icon: 'none' })
      }
    })
  },

  /** 输入过程中记录草稿（不请求后端，避免每敲一个字就提交） */
  onNicknameChange(e) {
    this.setData({ nicknameDraft: e.detail.value || '' })
  },

  /** 昵称输入框失焦 / 回车时保存 */
  onNicknameBlur(e) {
    this.setData({ nicknameDraft: e.detail.value || '' })
    this.saveNicknameIfChanged()
  },

  /** 昵称有变化才提交，避免无意义请求 */
  saveNicknameIfChanged() {
    const nickname = (this.data.nicknameDraft || '').trim()
    const current = (this.data.userInfo && this.data.userInfo.nickname) || ''
    if (!nickname || nickname === current) return

    const app = getApp()
    // 记录本次请求，供 loadProfile 判断是否有未完成的保存
    this._savePromise = api.put('/auth/profile', { nickname }).then(userInfo => {
      const updated = { ...app.globalData.userInfo, ...userInfo }
      app.globalData.userInfo = updated
      wx.setStorageSync('userInfo', updated)
      this.setData({ userInfo: updated, nicknameDraft: userInfo.nickname || '' })
      wx.showToast({ title: '昵称已更新', icon: 'success' })
      return userInfo
    }).catch(() => {
      // 保存失败时回滚显示，避免界面与后端不一致
      this.setData({ nicknameDraft: current })
    })
    return this._savePromise
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
