// pages/my-questions/my-questions.js - 个人题库
const api = require('../../utils/api')

Page({
  data: {
    questions: [],
    loading: false,
    page: 1,
    total: 0,
    keyword: '',
    filterTech: '',
    filterDifficulty: '',
    filterMastery: '',
    showArchived: false,
    techOptions: ['其他'],
    difficultyOptions: [
      { label: '简单', value: 1 },
      { label: '中等', value: 2 },
      { label: '困难', value: 3 }
    ],
    masteryOptions: [
      { label: '未掌握', value: 0 },
      { label: '学习中', value: 1 },
      { label: '已掌握', value: 2 }
    ],
    stats: null,
    showFilter: false,
    viewMode: 'list' // list / card
  },

  onLoad() {
    this.loadTechStacks()
    this.loadQuestions()
  },

  loadTechStacks() {
    api.get('/questions/tech-stacks').then(res => {
      if (res.stacks && res.stacks.length > 0) {
        this.setData({ techOptions: res.stacks })
      }
    }).catch(err => {
      console.error('加载技术栈失败:', err)
      // 降级使用默认列表
      this.setData({
        techOptions: ['Python', 'Java', 'JavaScript', '前端', '后端', 'AI 大模型', '算法', '数据库', '其他']
      })
    })
  },

  onShow() {
    this.loadQuestions()
  },

  onPullDownRefresh() {
    this.setData({ page: 1, questions: [] })
    this.loadQuestions().then(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.questions.length < this.data.total) {
      this.setData({ page: this.data.page + 1 })
      this.loadQuestions()
    }
  },

  // 搜索
  onSearchInput(e) {
    this.setData({ keyword: e.detail.value })
  },
  doSearch() {
    this.setData({ page: 1, questions: [] })
    this.loadQuestions()
  },

  // 切换筛选面板
  toggleFilter() {
    this.setData({ showFilter: !this.data.showFilter })
  },

  // 筛选选项
  filterByTech(e) {
    const val = e.currentTarget.dataset.value
    this.setData({ filterTech: this.data.filterTech === val ? '' : val, page: 1, questions: [] })
    this.loadQuestions()
  },

  filterByDifficulty(e) {
    const val = e.currentTarget.dataset.value
    this.setData({ filterDifficulty: this.data.filterDifficulty === val ? '' : val, page: 1, questions: [] })
    this.loadQuestions()
  },

  filterByMastery(e) {
    const val = e.currentTarget.dataset.value
    this.setData({ filterMastery: this.data.filterMastery === val ? '' : val, page: 1, questions: [] })
    this.loadQuestions()
  },

  toggleArchived() {
    this.setData({ showArchived: !this.data.showArchived, page: 1, questions: [] })
    this.loadQuestions()
  },

  // 加载题目列表
  loadQuestions() {
    this.setData({ loading: true })
    const params = {
      page: this.data.page,
      size: 20,
      archived: this.data.showArchived
    }
    if (this.data.keyword) params.keyword = this.data.keyword
    if (this.data.filterTech) params.tech_stack = this.data.filterTech
    if (this.data.filterDifficulty) params.difficulty = this.data.filterDifficulty
    if (this.data.filterMastery !== '') params.mastery = this.data.filterMastery

    return api.get('/questions/', params).then(res => {
      const items = res.items.map(q => ({
        ...q,
        difficultyLabel: ['', '简单', '中等', '困难'][q.difficulty],
        difficultyClass: ['', 'green', 'orange', 'red'][q.difficulty],
        masteryLabel: ['未掌握', '学习中', '已掌握'][q.mastery],
        masteryClass: ['gray', 'orange', 'green'][q.mastery]
      }))
      this.setData({
        questions: this.data.page === 1 ? items : [...this.data.questions, ...items],
        total: res.total,
        loading: false
      })
    }).catch(() => this.setData({ loading: false }))
  },

  // 切换掌握程度
  cycleMastery(e) {
    const id = e.currentTarget.dataset.id
    const current = e.currentTarget.dataset.mastery
    const next = (current + 1) % 3
    api.post(`/questions/${id}/mastery?mastery=${next}`).then(() => {
      wx.showToast({
        title: ['未掌握', '学习中', '已掌握'][next],
        icon: 'success'
      })
      this.loadQuestions()
    })
  },

  // 删除题目
  deleteQuestion(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '确认删除',
      content: '删除后无法恢复，确定删除吗？',
      success: (res) => {
        if (res.confirm) {
          api.del(`/questions/${id}`).then(() => {
            wx.showToast({ title: '已删除', icon: 'success' })
            this.loadQuestions()
          })
        }
      }
    })
  },

  // 跳转到题目详情
  goQuestionDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/question-detail/question-detail?id=${id}` })
  },

  // 发布题目到社区
  publishToCommunity(e) {
    const id = e.currentTarget.dataset.id
    // 找到题目数据
    const question = this.data.questions.find(q => q.id === id)
    if (!question) return

    wx.showModal({
      title: '发布到社区',
      content: '确定要将此题目发布到社区圈吗？',
      success: (res) => {
        if (res.confirm) {
          api.post('/posts/', {
            title: question.title,
            content: question.content,
            tech_stack: question.tech_stack,
            difficulty: question.difficulty,
            tags: question.tags || [],
            also_save_to_my: false
          }).then(() => {
            wx.showToast({ title: '发布成功', icon: 'success' })
          }).catch(err => {
            wx.showToast({ title: '发布失败', icon: 'none' })
          })
        }
      }
    })
  },

  // 切换视图模式
  toggleView() {
    this.setData({ viewMode: this.data.viewMode === 'list' ? 'card' : 'list' })
  },

  // 跳转到文件导入页面
  goFileImport() {
    wx.navigateTo({ url: '/pages/file-import/file-import' })
  }
})
