/**
 * 表格固定表头（sticky）公共配置。
 *
 * 布局是「侧栏固定 + 顶栏固定 + 仅内容区滚动」（见 AppLayout），
 * 滚动容器是 .ant-layout-content 而不是 window。rc-table 的计算逻辑
 * 默认监听 window 的 scroll，拿不到正确偏移，所以必须显式告知容器。
 *
 * 配套注意事项（改布局时勿踩）：
 * 1. 内容区 .ant-layout-content 与白色卡片都不能加 overflow: hidden，
 *    否则它们会取代内容区成为「最近滚动容器」且自身不滚动，sticky 直接失效。
 * 2. 内容区不能有 padding：Chrome 计算 sticky 约束矩形时会把滚动容器的
 *    内边距算进去，表头会比内容区顶部低一个 padding 的距离。
 */
export const stickyTableConfig = {
  getContainer: () =>
    (document.querySelector('.ant-layout-content') as HTMLElement | null) ??
    document.body,
}
