// app.js - 知问库小程序入口
const { login } = require('./utils/auth')

App({
  globalData: {
    userInfo: null,
    token: '',
    baseUrl: 'http://192.168.31.138:8000/api' // 后端地址, 开发时用本地
  },

  onLaunch() {
    // 尝试从本地恢复登录态
    const token = wx.getStorageSync('token')
    const userInfo = wx.getStorageSync('userInfo')
    if (token && userInfo) {
      this.globalData.token = token
      this.globalData.userInfo = userInfo
    } else {
      this.doLogin()
    }
  },

  doLogin() {
    login().then(res => {
      this.globalData.token = res.token
      this.globalData.userInfo = res
      wx.setStorageSync('token', res.token)
      wx.setStorageSync('userInfo', res)
    }).catch(err => {
      console.error('登录失败', err)
    })
  }
})
