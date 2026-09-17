// pages/public-questions/public-questions.js - 公共题库首页（技术栈图标网格）
const api = require('../../utils/api')

Page({
  data: {
    techStacks: [],
    // 技术栈分组
    techGroups: [
      {
        name: '编程语言',
        icon: '💻',
        items: ['Python', 'Java', 'Go', 'C/C++', 'Rust', 'JavaScript', 'TypeScript']
      },
      {
        name: '前端',
        icon: '🎨',
        items: ['React', 'Vue', 'Angular', 'HTML/CSS', '小程序', 'Node.js']
      },
      {
        name: '后端框架',
        icon: '⚙️',
        items: ['Django', 'Flask', 'FastAPI', 'Spring Boot', 'Express', 'Gin']
      },
      {
        name: 'AI & 数据',
        icon: '🤖',
        items: ['AI 大模型', '机器学习', '深度学习', 'NLP', '计算机视觉', '数据分析']
      },
      {
        name: '数据库',
        icon: '🗄️',
        items: ['MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Elasticsearch']
      },
      {
        name: '基础设施',
        icon: '️',
        items: ['Docker', 'Kubernetes', 'Linux', 'Nginx', 'DevOps', 'CI/CD']
      },
      {
        name: '网络 & 安全',
        icon: '🔒',
        items: ['TCP/IP', 'HTTP', '网络安全', '密码学']
      },
      {
        name: '其他',
        icon: '',
        items: ['算法', '数据结构', '操作系统', '分布式系统', '微服务', '测试', '其他']
      }
    ]
  },

  onLoad() {
    this.loadTechStacks()
  },

  loadTechStacks() {
    api.get('/questions/tech-stacks').then(res => {
      if (res.stacks && res.stacks.length > 0) {
        // 用后端返回的列表更新分组
        const allStacks = res.stacks
        const groups = this.data.techGroups.map(g => ({
          ...g,
          items: g.items.filter(item => allStacks.includes(item))
        })).filter(g => g.items.length > 0)
        this.setData({ techStacks: allStacks, techGroups: groups })
      }
    }).catch(() => {})
  },

  goTechList(e) {
    const tech = e.currentTarget.dataset.tech
    wx.navigateTo({ url: `/pages/public-tech-list/public-tech-list?tech=${encodeURIComponent(tech)}` })
  }
})
