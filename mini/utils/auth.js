// utils/auth.js - 微信登录
const api = require('./api')

function login() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(loginRes) {
        // 获取用户信息
        wx.getUserProfile({
          desc: '用于展示个人信息',
          success(profileRes) {
            api.post('/auth/login', {
              code: loginRes.code,
              nickname: profileRes.userInfo.nickName || '',
              avatar_url: profileRes.userInfo.avatarUrl || ''
            }).then(resolve).catch(reject)
          },
          fail() {
            // 用户拒绝授权, 仍然用 code 登录
            api.post('/auth/login', {
              code: loginRes.code
            }).then(resolve).catch(reject)
          }
        })
      },
      fail: reject
    })
  })
}

module.exports = { login }
