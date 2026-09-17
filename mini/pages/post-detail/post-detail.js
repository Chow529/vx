// pages/post-detail/post-detail.js - 帖子详情页（含评论）
const api = require('../../utils/api')

Page({
  data: {
    postId: 0,
    post: null,
    comments: [],
    commentText: '',
    loading: true
  },

  onLoad(options) {
    const postId = Number(options.id)
    this.setData({ postId })
    this.loadPost()
    this.loadComments()
  },

  loadPost() {
    api.get(`/posts/${this.data.postId}`).then(res => {
      this.setData({
        post: {
          ...res,
          difficultyLabel: ['', '简单', '中等', '困难'][res.difficulty],
          difficultyClass: ['', 'green', 'orange', 'red'][res.difficulty],
          timeAgo: formatTime(res.created_at)
        },
        loading: false
      })
    }).catch(() => this.setData({ loading: false }))
  },

  loadComments() {
    api.get(`/posts/${this.data.postId}/comments`).then(res => {
      this.setData({ comments: res || [] })
    }).catch(() => {})
  },

  onCommentInput(e) {
    this.setData({ commentText: e.detail.value })
  },

  submitComment() {
    const content = this.data.commentText.trim()
    if (!content) {
      wx.showToast({ title: '请输入评论内容', icon: 'none' })
      return
    }
    api.post(`/posts/${this.data.postId}/comments`, { content }).then(() => {
      this.setData({ commentText: '' })
      wx.showToast({ title: '评论成功', icon: 'success' })
      this.loadComments()
      this.loadPost()
    })
  },

  likePost() {
    api.post(`/posts/${this.data.postId}/like`).then(res => {
      this.setData({ 'post.like_count': res.like_count })
      wx.showToast({ title: '点赞成功', icon: 'success' })
    })
  },

  likeComment(e) {
    const commentId = e.currentTarget.dataset.id
    api.post(`/posts/${this.data.postId}/comments/${commentId}/like`).then(res => {
      this.loadComments()
    })
  },

  collectToMy() {
    api.post(`/questions/collect/${this.data.postId}`, {
      post_id: this.data.postId,
      difficulty: this.data.post.difficulty
    }).then(() => {
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
