// pages/index/index.js - 社区圈首页
const api = require('../../utils/api')

Page({
  data: {
    posts: [],
    loading: false,
    page: 1,
    total: 0,
    sort: 'latest', // latest / hot / unsolved
    sortOptions: [
      { label: '最新', value: 'latest' },
      { label: '最热', value: 'hot' },
      { label: '未解决', value: 'unsolved' }
    ],
    currentSort: 0
  },

  onLoad() {
    this.loadPosts()
  },

  onPullDownRefresh() {
    this.setData({ page: 1, posts: [] })
    this.loadPosts().then(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.posts.length < this.data.total) {
      this.setData({ page: this.data.page + 1 })
      this.loadPosts()
    }
  },

  switchSort(e) {
    const idx = e.currentTarget.dataset.index
    this.setData({
      currentSort: idx,
      sort: this.data.sortOptions[idx].value,
      page: 1,
      posts: []
    })
    this.loadPosts()
  },

  loadPosts() {
    this.setData({ loading: true })
    return api.get('/posts/', {
      sort: this.data.sort,
      page: this.data.page,
      size: 20
    }).then(res => {
      const newPosts = res.items.map(p => ({
        ...p,
        difficultyLabel: ['', '简单', '中等', '困难'][p.difficulty],
        difficultyClass: ['', 'green', 'orange', 'red'][p.difficulty],
        timeAgo: formatTime(p.created_at)
      }))
      this.setData({
        posts: this.data.page === 1 ? newPosts : [...this.data.posts, ...newPosts],
        total: res.total,
        loading: false
      })
    }).catch(() => this.setData({ loading: false }))
  },

  goPostDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/post-detail/post-detail?id=${id}` })
  },

  likePost(e) {
    const id = e.currentTarget.dataset.id
    api.post(`/posts/${id}/like`).then(res => {
      wx.showToast({ title: '点赞成功', icon: 'success' })
    })
  },

  collectToMy(e) {
    const postId = e.currentTarget.dataset.id
    api.post(`/questions/collect/${postId}`, { post_id: postId, difficulty: 1 }).then(() => {
      wx.showToast({ title: '已存入题库', icon: 'success' })
    })
  }
})

function formatTime(dateStr) {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = (now - date) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff / 60) + '分钟前'
  if (diff < 86400) return Math.floor(diff / 3600) + '小时前'
  if (diff < 2592000) return Math.floor(diff / 86400) + '天前'
  return date.toLocaleDateString()
}
