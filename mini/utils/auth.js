// utils/auth.js - 微信登录
const api = require('./api')

/**
 * 微信登录
 *
 * 注意：微信已于 2022-10-25 收回 wx.getUserProfile 接口，
 * 调用它只会返回默认灰色头像和「微信用户」这个假昵称，
 * 所以这里不再请求昵称头像，只做 code 换 token。
 * 昵称头像改由用户在「我的」页面通过「头像昵称填写能力」主动完善。
 */
function login() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(loginRes) {
        api.post('/auth/login', { code: loginRes.code })
          .then(resolve)
          .catch(reject)
      },
      fail: reject
    })
  })
}

module.exports = { login }
