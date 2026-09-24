// pages/post-detail/post-detail.js - 帖子详情页（含评论）
const api = require('../../utils/api')

Page({
  data: {
    postId: 0,
    post: null,
    comments: [],
    commentText: '',
    loading: true,
    showEdit: false,
    editTitle: '',
    editContent: '',
    editAnswer: '',
    editing: false
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
      this.setData({
        'post.like_count': res.like_count,
        'post.is_liked': res.liked
      })
    })
  },

  likeComment(e) {
    const commentId = e.currentTarget.dataset.id
    api.post(`/posts/${this.data.postId}/comments/${commentId}/like`).then(res => {
      const comments = this.data.comments.map(c =>
        c.id === commentId ? { ...c, like_count: res.like_count, is_liked: res.liked } : c
      )
      this.setData({ comments })
    })
  },

  collectToMy() {
    const post = this.data.post
    // 发布时已勾选存入题库的，不能重复收藏
    if (post && post.is_own && post.is_collected) {
      wx.showToast({ title: '该题目已在你的题库中', icon: 'none' })
      return
    }
    api.post(`/questions/collect/${this.data.postId}`, {
      post_id: this.data.postId,
      difficulty: post.difficulty
    }).then(res => {
      this.setData({ 'post.is_collected': res.collected })
      wx.showToast({
        title: res.collected ? '已存入题库' : '已取消收藏',
        icon: 'none'
      })
    })
  },

  // ─── 编辑帖子（本人或管理员）───
  openEdit() {
    const p = this.data.post
    this.setData({
      showEdit: true,
      editTitle: p.title,
      editContent: p.content,
      editAnswer: p.answer || ''
    })
  },

  closeEdit() {
    this.setData({ showEdit: false })
  },

  onEditTitleInput(e) { this.setData({ editTitle: e.detail.value }) },
  onEditContentInput(e) { this.setData({ editContent: e.detail.value }) },
  onEditAnswerInput(e) { this.setData({ editAnswer: e.detail.value }) },

  saveEdit() {
    const { editTitle, editContent, editAnswer } = this.data
    if (!editTitle.trim()) {
      wx.showToast({ title: '请输入标题', icon: 'none' })
      return
    }
    this.setData({ editing: true })
    api.put(`/posts/${this.data.postId}`, {
      title: editTitle.trim(),
      content: editContent.trim(),
      answer: editAnswer.trim()
    }).then(() => {
      wx.showToast({ title: '已保存', icon: 'success' })
      this.setData({ showEdit: false })
      this.loadPost()
    }).finally(() => this.setData({ editing: false }))
  },

  // ─── 删除评论（评论者/楼主/管理员）───
  deleteComment(e) {
    const commentId = e.currentTarget.dataset.id
    wx.showModal({
      title: '提示',
      content: '确定删除该评论？',
      success: res => {
        if (!res.confirm) return
        api.del(`/posts/${this.data.postId}/comments/${commentId}`).then(() => {
          wx.showToast({ title: '已删除', icon: 'none' })
          this.loadComments()
          this.loadPost()
        })
      }
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
