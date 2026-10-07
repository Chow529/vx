// app.js - 知问库小程序入口
const { login } = require('./utils/auth')

App({
  globalData: {
    userInfo: null,
    token: '',
    baseUrl: 'https://scruffy-whoops-cranial.ngrok-free.dev/' // 后端地址, 开发时用本地
  },

  onLaunch() {
    // 尝试从本地恢复登录态
    const token = wx.getStorageSync('token')
    const userInfo = wx.getStorageSync('userInfo')
    if (token) {
      this.globalData.token = token
      this.globalData.userInfo = userInfo || null
    }
    // 一进入小程序就执行登录；已登录则后台刷新一次用户信息
    // （确保 is_admin / 昵称 / 头像是最新的，不用重启小程序）
    this.ensureLogin()
      .then(() => this.refreshUserInfo())
      .catch(() => {})
  },

  /** 当前用户是否管理员（未登录 / 未加载时为 false） */
  isAdmin() {
    const u = this.globalData.userInfo
    return !!(u && u.is_admin)
  },

  /** 刷新用户信息（最新昵称 / 头像 / 声望 / 是否管理员） */
  refreshUserInfo() {
    if (!this.globalData.token) return Promise.resolve(null)
    if (this._mePromise) return this._mePromise

    const api = require('./utils/api')
    this._mePromise = api.get('/auth/me')
      .then(user => {
        this.globalData.userInfo = { ...this.globalData.userInfo, ...user }
        wx.setStorageSync('userInfo', this.globalData.userInfo)
        return this.globalData.userInfo
      })
      .catch(() => null)
      .then(res => {
        this._mePromise = null
        return res
      })
    return this._mePromise
  },

  /**
   * 确保登录完成，返回同一个 Promise（并发调用只登录一次）
   *
   * 关键：页面 onLoad 里的请求比登录先发出会导致 401，
   * 所以请求前必须先 await 这个方法。
   */
  ensureLogin() {
    if (this.globalData.token) return Promise.resolve(this.globalData)
    if (!this._loginPromise) {
      this._loginPromise = login()
        .then(res => {
          this.globalData.token = res.token
          this.globalData.userInfo = res
          wx.setStorageSync('token', res.token)
          wx.setStorageSync('userInfo', res)
          return this.globalData
        })
        .catch(err => {
          console.error('登录失败', err)
          this._loginPromise = null // 失败后允许下次重试
          throw err
        })
    }
    return this._loginPromise
  },

  /** 登录态失效时调用：清空后重新登录 */
  doLogin() {
    this._loginPromise = null
    this.globalData.token = ''
    this.globalData.userInfo = null
    wx.removeStorageSync('token')
    wx.removeStorageSync('userInfo')
    return this.ensureLogin()
  }
})
