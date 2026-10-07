// utils/api.js - 统一 API 请求封装

function getAppSafe() {
  return getApp()
}

function request(url, options = {}) {
  return new Promise((resolve, reject) => {
    const { method = 'GET', data, header = {}, noAuth = false } = options

    // 只有登录接口本身不需要 token，也不能等登录，
    // 否则会 登录接口 → ensureLogin → login → 登录接口 无限递归。
    // 其余 /auth/* （如 /auth/me、/auth/profile）都需要带 token。
    const needAuth = !noAuth && !url.startsWith('/auth/login')

    // 需要登录的接口：先等登录完成，避免 token 还没拿到就发请求导致 401
    const app0 = getAppSafe()
    const ready = (needAuth && app0 && app0.ensureLogin)
      ? app0.ensureLogin().catch(() => null)
      : Promise.resolve()

    ready.then(() => {
      const app = getAppSafe()
      const finalHeader = { ...header }

      // 自动带上 token
      if (needAuth && app && app.globalData && app.globalData.token) {
        finalHeader['Authorization'] = `Bearer ${app.globalData.token}`
      }
      finalHeader['Content-Type'] = finalHeader['Content-Type'] || 'application/json'

      wx.request({
        url: (app && app.globalData && app.globalData.baseUrl || 'http://127.0.0.1:8000/api') + url,
        method,
        data,
        header: finalHeader,
        success(res) {
          if (res.statusCode === 401 && needAuth) {
            // token 失效：清空后重新登录（下次请求会带上新 token）
            if (app && app.doLogin) app.doLogin().catch(() => {})
            reject(new Error('登录已过期'))
            return
          }
          if (res.statusCode >= 400) {
            const msg = (res.data && res.data.detail) || '请求失败'
            wx.showToast({ title: msg, icon: 'none' })
            reject(new Error(msg))
            return
          }
          resolve(res.data)
        },
        fail(err) {
          wx.showToast({ title: '网络错误', icon: 'none' })
          reject(err)
        }
      })
    })
  })
}

// 便捷方法
const api = {
  get: (url, data) => request(url, { method: 'GET', data }),
  post: (url, data) => request(url, { method: 'POST', data }),
  put: (url, data) => request(url, { method: 'PUT', data }),
  del: (url, data) => request(url, { method: 'DELETE', data })
}

module.exports = api
