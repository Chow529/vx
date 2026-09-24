// pages/index/index.js - 社区圈首页
const api = require('../../utils/api')

Page({
  data: {
    posts: [],
    loading: false,
    page: 1,
    total: 0,
    sort: 'latest', // latest / hot / mine
    sortOptions: [
      { label: '最新', value: 'latest' },
      { label: '最热', value: 'hot' },
      { label: '我的', value: 'mine' }
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
    const params = { page: this.data.page, size: 20 }
    if (this.data.sort === 'mine') {
      // 「我的」标签：只看自己发布的，按最新排序
      params.mine = true
      params.sort = 'latest'
    } else {
      params.sort = this.data.sort
    }
    return api.get('/posts/', params).then(res => {
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
      // 切换本地状态
      const posts = this.data.posts.map(p => {
        if (p.id === id) {
          return { ...p, is_liked: res.liked, like_count: res.like_count }
        }
        return p
      })
      this.setData({ posts })
    })
  },

  collectToMy(e) {
    const postId = e.currentTarget.dataset.id
    const post = this.data.posts.find(p => p.id === postId)
    // 发布时已勾选存入题库的，不能重复收藏
    if (post && post.is_own && post.is_collected) {
      wx.showToast({ title: '该题目已在你的题库中', icon: 'none' })
      return
    }
    api.post(`/questions/collect/${postId}`, { post_id: postId, difficulty: 1 }).then(res => {
      // 切换本地收藏状态
      const posts = this.data.posts.map(p =>
        p.id === postId ? { ...p, is_collected: res.collected } : p
      )
      this.setData({ posts })
      wx.showToast({
        title: res.collected ? `已存入题库${res.remaining_today != null ? '（今日剩余' + res.remaining_today + '）' : ''}` : '已取消收藏',
        icon: 'none'
      })
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
