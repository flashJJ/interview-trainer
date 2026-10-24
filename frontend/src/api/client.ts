/**
 * API 聚合出口（向后兼容层）。
 *
 * 实现已按业务域拆分到同目录各文件；页面可继续从 '../api/client' 导入，
 * 也可直接按域导入（推荐新代码使用按域导入）。
 */
export { http, TOKEN_KEY, errMsg } from './http'
export { authApi } from './auth'
export { knowledgeApi } from './knowledge'
export { questionApi } from './questions'
export { examApi } from './exams'
export { analyticsApi } from './analytics'
export { settingsApi } from './settings'
export { wrongQuestionsApi } from './wrong-questions'
export { chatApi } from './chat'
