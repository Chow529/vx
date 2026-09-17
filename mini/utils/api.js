// utils/api.js - 统一 API 请求封装

function getAppSafe() {
  return getApp()
}

function request(url, options = {}) {
  return new Promise((resolve, reject) => {
    const { method = 'GET', data, header = {} } = options
    const app = getAppSafe()

    // 自动带上 token
    if (app && app.globalData && app.globalData.token) {
      header['Authorization'] = `Bearer ${app.globalData.token}`
    }
    header['Content-Type'] = header['Content-Type'] || 'application/json'

    wx.request({
      url: (app && app.globalData && app.globalData.baseUrl || 'http://127.0.0.1:8000/api') + url,
      method,
      data,
      header,
      success(res) {
        if (res.statusCode === 401) {
          // token 过期, 重新登录
          if (app && app.doLogin) app.doLogin()
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
}

// 便捷方法
const api = {
  get: (url, data) => request(url, { method: 'GET', data }),
  post: (url, data) => request(url, { method: 'POST', data }),
  put: (url, data) => request(url, { method: 'PUT', data }),
  del: (url, data) => request(url, { method: 'DELETE', data }),

  // 上传文件
  upload: (url, filePath, name = 'file') => {
    return new Promise((resolve, reject) => {
      const app = getAppSafe()
      wx.uploadFile({
        url: (app && app.globalData && app.globalData.baseUrl || 'http://127.0.0.1:8000/api') + url,
        filePath,
        name,
        header: {
          'Authorization': app && app.globalData ? `Bearer ${app.globalData.token}` : ''
        },
        success(res) {
          try {
            const data = JSON.parse(res.data)
            resolve(data)
          } catch (e) {
            reject(new Error('解析响应失败'))
          }
        },
        fail: reject
      })
    })
  }
}

module.exports = api
