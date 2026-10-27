/* E2E 验证：登录 -> 知识库 -> 题库 -> 分析看板 -> 完整考试流程。
   注意：AntD Button 会在两个汉字间插入空格（如「登 录」），
   统一用 getByRole + name 正则匹配（可访问名会归一化空白）。

   运行前提：
   1. 后端 uvicorn 运行于 8000，前端 vite dev 运行于 5173
   2. 任意目录执行：npm install playwright（驱动系统 Edge，无需下载浏览器）
   3. node e2e_test.js（脚本输出截图到 docs/screenshots/） */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = 'http://localhost:5173';
// 相对脚本位置解析，避免把本机绝对路径写进开源仓库
const OUT = path.resolve(__dirname, '../../docs/screenshots');

(async () => {
  fs.mkdirSync(OUT, { recursive: true });

  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error' && !msg.text().includes('favicon')) consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => consoleErrors.push('PAGEERROR: ' + err.message));

  const report = [];
  const step = async (name, fn) => {
    try {
      await fn();
      report.push(`PASS  ${name}`);
    } catch (err) {
      report.push(`FAIL  ${name}  -> ${String(err.message).split('\n')[0]}`);
    }
  };
  const menuClick = (nameRe) => page.getByRole('menuitem', { name: nameRe }).first().click();

  await step('打开登录页', async () => {
    await page.goto(BASE + '/login', { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: /登\s*录/ }).waitFor({ timeout: 10000 });
  });
  await page.screenshot({ path: `${OUT}/01-login.png` });

  await step('登录 demo 账号', async () => {
    await page.fill('input[placeholder="请输入用户名"]', 'demo');
    await page.fill('input[placeholder="请输入密码"]', 'demo123');
    await page.getByRole('button', { name: /登\s*录/ }).click();
    await page.waitForURL('**/knowledge', { timeout: 15000 });
  });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/02-knowledge.png` });

  await step('知识库列表渲染（内置语料与种子资料可见）', async () => {
    // 列表默认按 id 倒序，首页是后载入的内置语料
    await page.getByText('向量检索与 Embedding 工程实践').first().waitFor({ timeout: 10000 });
    await page.getByText('AI 应用评测：指标、评测集与回归').first().waitFor({ timeout: 5000 });
    // 资料条数随内置语料扩充变化，这里只校验至少 8 条而非写死数字
    const rowCount = await page.locator('.ant-table-tbody tr').count();
    if (rowCount < 8) throw new Error(`知识库表格行数异常：${rowCount}`);
  });

  await step('网页链接录入（错误路径：不可达地址友好提示）', async () => {
    await page.getByRole('button', { name: /新\s*建\s*知\s*识\s*库/ }).click();
    const createModal = page.getByRole('dialog');
    await createModal.waitFor({ timeout: 5000 });
    await createModal.getByRole('tab', { name: /网\s*页\s*链\s*接/ }).click();
    await createModal.getByPlaceholder('例如 https://example.com/article').fill('http://127.0.0.1:9/none');
    await createModal.getByRole('button', { name: /抓\s*取\s*并\s*处\s*理/ }).click();
    // 不可达地址应弹出友好错误（而不是白屏或无限转圈）
    await page.getByText(/网络请求失败|抓取超时|无法连接/).first().waitFor({ timeout: 30000 });
    await createModal.getByRole('button', { name: /取\s*消/ }).click();
    await page.waitForTimeout(500);
  });

  await step('题库页渲染', async () => {
    await menuClick(/题\s*库/);
    await page.locator('table').first().waitFor({ timeout: 10000 });
    await page.waitForTimeout(1500);
  });
  await page.screenshot({ path: `${OUT}/03-questions.png` });

  await step('出题审核流（知识库出题 -> 待审核 -> 通过入池）', async () => {
    // 出题去重按「用户 + 内容」判定：反复跑同一个库时，固定资料的题目会被全部跳过
    // （created=0），待审队列于是为空——那是测试数据问题，不是功能缺陷。
    // 所以先造一条带时间戳的唯一资料，保证本步每次都有新题进待审。
    const sampleTitle = `E2E 审核流样本 ${Date.now()}`;
    const sample = await page.evaluate(async (title) => {
      const token = localStorage.getItem('it_token');
      const resp = await fetch('/api/knowledge/entries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title,
          content:
            `${title}。本节讨论 HTTP 缓存策略：Cache-Control 的 max-age 指定新鲜期，` +
            `no-store 表示完全不缓存；ETag 用于协商缓存，返回 304 表示可复用本地副本。` +
            `编号 ${title.slice(-13)} 的样本仅用于端到端测试出题链路，不承载真实业务含义。`,
        }),
      });
      if (!resp.ok) throw new Error(`创建测试资料失败：${await resp.text()}`);
      return resp.json();
    }, sampleTitle);
    if (!sample.id) throw new Error('创建测试资料未返回 id');

    // 1. 知识库列表按 id 倒序，新建资料即首行；对该行 AI 出题（默认全题型，每题型 2 道）
    await menuClick(/知\s*识\s*库/);
    await page.locator('.ant-table-tbody tr:has(td)').first().waitFor({ timeout: 10000 });
    const firstRow = page.locator('.ant-table-tbody tr:has(td)').first();
    if (!(await firstRow.textContent()).includes(sampleTitle)) {
      // 缓存命中导致列表未刷新时，重载一次（新建条目一定在首位）
      await page.reload();
      await page.locator('.ant-table-tbody tr:has(td)').first().waitFor({ timeout: 10000 });
    }
    await firstRow.getByRole('button', { name: /AI\s*出\s*题/ }).click();
    const genModal = page.getByRole('dialog');
    await genModal.waitFor({ timeout: 5000 });
    await genModal.getByRole('spinbutton').fill('2');
    await genModal.getByRole('button', { name: /开\s*始\s*生\s*成/ }).click();
    await page.getByText(/已生成/).first().waitFor({ timeout: 180000 }); // 真实 LLM 出题 6 题需要较长时间
    await page.waitForTimeout(500);
    // 2. 进入题目审核页，待审列表应有题
    await menuClick(/题\s*目\s*审\s*核/);
    await page.getByText('待审核题目').first().waitFor({ timeout: 10000 });
    await page.locator('.ant-table-tbody tr:has(td)').first().waitFor({ timeout: 10000 });
    // 待审总数（统计卡口径，避免分页补位导致行数不变）
    const pendingStat = page
      .locator('.ant-statistic')
      .filter({ hasText: '待审核题目' })
      .locator('.ant-statistic-content-value');
    const pendingBefore = Number((await pendingStat.textContent()) ?? '0');
    if (pendingBefore === 0) throw new Error('待审核列表为空，出题未进入审核队列');
    // 3. 通过第一题，待审总数减少（图标 aria-label 会混入可访问名，故在行内用子串匹配）
    const firstPendingRow = page.locator('.ant-table-tbody tr:has(td)').first();
    await firstPendingRow.getByRole('button', { name: /通\s*过/ }).first().click();
    await page.waitForTimeout(2000);
    const pendingAfter = Number((await pendingStat.textContent()) ?? '0');
    if (pendingAfter >= pendingBefore) {
      throw new Error(`审核通过后待审数未减少（${pendingBefore} -> ${pendingAfter}）`);
    }
    await page.waitForTimeout(1000);
  });
  await page.screenshot({ path: `${OUT}/11-review.png`, fullPage: true });

  await step('做题训练页渲染', async () => {
    await menuClick(/做\s*题\s*训\s*练/);
    await page.getByText('生成随机考卷').waitFor({ timeout: 10000 });
    await page.waitForTimeout(1500);
  });
  await page.screenshot({ path: `${OUT}/04-practice.png` });

  await step('题目分析平台渲染图表', async () => {
    await menuClick(/题\s*目\s*分\s*析/);
    await page.locator('canvas').first().waitFor({ timeout: 15000 });
    await page.waitForTimeout(2000);
  });
  await page.screenshot({ path: `${OUT}/05-question-analytics.png`, fullPage: true });

  await step('做题分析平台渲染图表', async () => {
    await menuClick(/做\s*题\s*分\s*析/);
    await page.locator('canvas').first().waitFor({ timeout: 15000 });
    await page.waitForTimeout(2000);
  });
  await page.screenshot({ path: `${OUT}/06-practice-analytics.png`, fullPage: true });

  await step('完整考试流程（组卷 -> 答题 -> 自动保存 -> 评分）', async () => {
    await menuClick(/做\s*题\s*训\s*练/);
    await page.getByText('生成随机考卷').waitFor();
    const card = page.locator('.ant-card:has-text("生成随机考卷")');
    await card.locator('.ant-input-number-input').fill('5');
    await page.getByRole('button', { name: /生\s*成\s*考\s*卷/ }).click();
    await page.waitForURL('**/exam/**', { timeout: 15000 });
    await page.getByRole('button', { name: /提\s*交\s*答\s*卷/ }).waitFor({ timeout: 10000 });

    const radios = await page.$$('.ant-radio-input');
    if (radios.length > 0) await radios[0].check();
    const inputs = await page.$$('input[placeholder="请输入答案"]');
    if (inputs.length > 0) await inputs[0].fill('布隆过滤器');
    await page.waitForTimeout(600);

    // 断言 1：「已作答」统计 > 0（修复 useWatch 失效前这里恒为 0）
    const answeredStat = page.locator('.ant-statistic').filter({ hasText: '已作答' }).locator('.ant-statistic-content-value');
    const answeredCount = Number((await answeredStat.textContent()) ?? '0');
    if (!(answeredCount > 0)) {
      throw new Error(`「已作答」统计为 ${answeredCount}，答案选择未生效`);
    }

    // 断言 2：改选答案后提交，提交的必须是改选后的值（覆盖"改了但提交旧值/空值"场景）
    let expectedAnswer = '';
    if (radios.length > 1) {
      await radios[1].check();
      expectedAnswer = await page.evaluate(() => document.querySelectorAll('.ant-radio-input')[1]?.value ?? '');
    } else if (inputs.length > 0) {
      expectedAnswer = '布隆过滤器';
    }

    await page.screenshot({ path: `${OUT}/07-exam.png` });
    await page.getByRole('button', { name: /提\s*交\s*答\s*卷/ }).click();
    await page.getByText('确认提交答卷').waitFor({ timeout: 5000 });
    const modalText = await page.locator('.ant-modal-body').innerText();
    const matched = modalText.match(/已作答\s*(\d+)\s*题/);
    if (!matched || Number(matched[1]) <= 0) {
      throw new Error(`确认弹窗未显示已作答题目：${modalText.slice(0, 80)}`);
    }
    await page.getByRole('button', { name: /确\s*认\s*提\s*交/ }).click();
    await page.waitForURL('**/result/**', { timeout: 20000 });
    await page.getByText('得分率').first().waitFor({ timeout: 10000 });

    // 断言 3：从 API 拉取成绩，确认提交的 user_answer 非空，且改选/填写的值确实出现在提交记录中
    const sessionId = page.url().split('/result/')[1];
    const detail = await page.evaluate(async (sid) => {
      const token = localStorage.getItem('it_token');
      const resp = await fetch(`/api/exams/sessions/${sid}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return resp.json();
    }, sessionId);
    const answered = detail.results.filter((r) => r.user_answer && r.user_answer.trim());
    if (answered.length === 0) {
      throw new Error('提交后所有题目的 user_answer 均为空——答案丢失');
    }
    if (expectedAnswer && !answered.some((r) => r.user_answer === expectedAnswer)) {
      throw new Error(
        `提交记录中找不到所选答案「${expectedAnswer}」：${JSON.stringify(answered.map((r) => r.user_answer))}`,
      );
    }
    await page.waitForTimeout(1500);
  });
  await page.screenshot({ path: `${OUT}/08-result.png`, fullPage: true });

  await step('AI 讲题（已配置 LLM：打开抽屉、发送消息、流式回复）', async () => {
    // 前置检查：未配置 LLM 时跳过（讲题属于可选能力，依赖外部 API Key）
    const llmEnabled = await page.evaluate(async () => {
      const token = localStorage.getItem('it_token');
      const r = await fetch('/api/settings', { headers: { Authorization: `Bearer ${token}` } });
      const cfg = await r.json();
      return cfg.llm_enabled;
    });
    if (!llmEnabled) {
      console.log('    SKIP  未配置 LLM，跳过讲题真实链路验证');
      return;
    }
    // 当前在考试结果页：点第一题「问 AI」
    await page.getByRole('button', { name: /问\s*AI/ }).first().click();
    const drawer = page.getByRole('dialog');
    await drawer.waitFor({ timeout: 10000 });
    const tutorInput = drawer.locator('input').first();
    await tutorInput.waitFor({ timeout: 10000 });
    // 抽屉打开时会异步拉取 LLM 状态与会话，输入框在初始化完成前是禁用态——轮询等待可用
    let enabled = false;
    for (let i = 0; i < 30; i++) {
      if (!(await tutorInput.isDisabled())) {
        enabled = true;
        break;
      }
      await page.waitForTimeout(500);
    }
    if (!enabled) {
      throw new Error('讲题输入框一直禁用（LLM 状态或会话初始化失败）');
    }
    // 真实发送一条消息，验证 SSE 流式回复
    await tutorInput.fill('这道题为什么是这个答案？请简要讲解');
    await drawer.getByRole('button', { name: /发\s*送/ }).click();
    // 等待助手回复出现（推理模型可能较慢，给 120s）
    await drawer.locator('span:has-text("AI 老师")').first().waitFor({ timeout: 120000 });
    await page.waitForTimeout(3000);
    const drawerText = await drawer.innerText();
    if (drawerText.length < 200) {
      throw new Error(`讲题回复内容过短：${drawerText.slice(0, 100)}`);
    }
    await page.keyboard.press('Escape');
    // 抽屉关闭动画 + 遮罩移除需要一点时间；直接导航回知识库页，避免遮罩残影影响后续菜单点击
    await page.goto('http://localhost:5173/knowledge', { waitUntil: 'networkidle' });
    await page.getByRole('menuitem', { name: /知\s*识\s*库/ }).waitFor({ timeout: 10000 });
  });

  await step('系统配置页渲染（模式展示 + LLM/Embedding 表单）', async () => {
    await menuClick(/系\s*统\s*配\s*置/);
    await page.getByText('AI 模型配置').first().waitFor({ timeout: 10000 });
    await page.getByText(/演示模式|AI 模式/).first().waitFor({ timeout: 5000 });
    await page.getByRole('button', { name: /测\s*试\s*LLM\s*连\s*接/ }).waitFor({ timeout: 5000 });
    await page.waitForTimeout(1500);
  });
  await page.screenshot({ path: `${OUT}/09-settings.png`, fullPage: true });

  await step('错题本页渲染（统计卡 + SM-2 排期列表）', async () => {
    await menuClick(/错\s*题\s*本/);
    await page.getByText('错题本').first().waitFor({ timeout: 10000 });
    await page.getByText('错题总数').first().waitFor({ timeout: 5000 });
    await page.locator('table').first().waitFor({ timeout: 5000 });
    await page.waitForTimeout(1500);
  });
  await page.screenshot({ path: `${OUT}/10-wrong-questions.png`, fullPage: true });

  await step('检索评测页（混合检索对比图 + 评测集 + 明细抽屉）', async () => {
    await menuClick(/检\s*索\s*评\s*测/);
    await page.getByText('检索评测').first().waitFor({ timeout: 10000 });
    await page.getByText('评测口径').waitFor({ timeout: 5000 });

    // 已有评测历史时才能验证图表与明细；空库只验证页面骨架（不硬造数据）
    const detailBtn = page.getByRole('button', { name: '明细' });
    if ((await detailBtn.count()) > 0) {
      await page.locator('canvas').first().waitFor({ timeout: 8000 });
      await detailBtn.first().click();
      await page.getByText(/评测明细/).first().waitFor({ timeout: 8000 });
      // 明细里必须能看到逐模式的召回标记
      await page.getByText(/^R=/).first().waitFor({ timeout: 8000 });
      await page.keyboard.press('Escape');
      await page.waitForTimeout(600);
    }
    await page.waitForTimeout(800);
  });
  await page.screenshot({ path: `${OUT}/12-retrieval.png`, fullPage: true });

  await step('掌握度页（雷达图 + 维度明细 + 一键定向练习）', async () => {
    await menuClick(/掌\s*握\s*度/);
    await page.getByText('知识点掌握度').first().waitFor({ timeout: 10000 });
    await page.getByText('掌握度口径').waitFor({ timeout: 5000 });
    await page.getByText('综合掌握度').first().waitFor({ timeout: 5000 });

    // 雷达图（ECharts canvas）
    await page.locator('canvas').first().waitFor({ timeout: 10000 });
    await page.waitForTimeout(1200);

    // 维度明细表：默认按资料，种子资料均应在列
    const rowCount = await page.locator('.ant-table-tbody tr').count();
    if (rowCount < 1) throw new Error(`维度明细表无数据行：${rowCount}`);
    // 页面本身先截一张（组卷成功后会跳转到考试页）
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${OUT}/13-mastery.png`, fullPage: true });

    // 薄弱项「一键练习」优先；没有薄弱项时退回维度表首行的「针对性练习」
    let practiceBtn = page.getByRole('button', { name: /一\s*键\s*练\s*习/ }).first();
    if ((await practiceBtn.count()) === 0) {
      practiceBtn = page.getByRole('button', { name: /针\s*对\s*性\s*练\s*习/ }).first();
    }
    if ((await practiceBtn.count()) === 0) throw new Error('未找到定向练习入口');
    await practiceBtn.click();
    await page.getByText(/针对性练习 ·/).first().waitFor({ timeout: 8000 });
    await page.getByRole('button', { name: /组\s*卷\s*并\s*开\s*始/ }).click();
    await page.waitForURL('**/exam/**', { timeout: 15000 });
    await page.waitForTimeout(1200);
  });
  await page.screenshot({ path: `${OUT}/14-targeted-exam.png`, fullPage: true });

  await step('内置内容开箱即用（题库来源筛选 + 知识库内置徽标）', async () => {
    // 1. 题库页按来源筛选「内置精选」，确认徽标与题量
    await menuClick(/题\s*库/);
    await page.locator('table').first().waitFor({ timeout: 10000 });
    const sourceSelect = page
      .locator('.ant-form-item')
      .filter({ hasText: '来源' })
      .locator('.ant-select');
    await sourceSelect.click();
    await page.locator('.ant-select-item-option', { hasText: '内置精选' }).first().click();
    await page.getByRole('button', { name: /搜\s*索/ }).click();
    await page.waitForTimeout(1500);
    const builtinTags = await page.locator('.ant-tag', { hasText: '内置精选' }).count();
    if (builtinTags === 0) throw new Error('题库未出现「内置精选」来源徽标');
    await page.screenshot({ path: `${OUT}/15-builtin-questions.png`, fullPage: true });

    // 2. 知识库页确认内置语料带「内置」徽标
    await menuClick(/知\s*识\s*库/);
    await page.locator('table').first().waitFor({ timeout: 10000 });
    await page.waitForTimeout(1200);
    const entryTags = await page.locator('.ant-tag', { hasText: /^内置$/ }).count();
    if (entryTags === 0) throw new Error('知识库未出现「内置」来源徽标');
    await page.screenshot({ path: `${OUT}/16-builtin-knowledge.png`, fullPage: true });
  });

  await step('难度蓝图自适应组卷（选「夯实」→ 生成 → 校验模式/比例）', async () => {
    await menuClick(/做\s*题\s*训\s*练/);
    await page.getByText('生成随机考卷').waitFor({ timeout: 10000 });
    const card = page.locator('.ant-card:has-text("生成随机考卷")');

    // 选难度蓝图 = 夯实（与「难度」互斥，选蓝图后难度应被禁用）
    const bpSelect = card
      .locator('.ant-form-item')
      .filter({ hasText: '难度蓝图' })
      .locator('.ant-select');
    await bpSelect.click();
    await page.locator('.ant-select-item-option', { hasText: '夯实' }).first().click();
    await page.waitForTimeout(300);

    // 题量设 10（蓝图按比例分配：易2 / 中6 / 难2）
    await card.locator('.ant-input-number-input').fill('10');
    await card.getByRole('button', { name: /生\s*成\s*考\s*卷\s*并\s*开\s*始/ }).click();
    await page.waitForURL('**/exam/**', { timeout: 15000 });

    // 通过 API 校验 config.mode=adaptive，actual_mix 之和等于题量，且蓝图名进入标题
    // 注意：/exams/{paper_id} 返回 { paper: {...} }，config 在 paper 下
    const paperId = page.url().split('/exam/')[1];
    const detail = await page.evaluate(async (pid) => {
      const token = localStorage.getItem('it_token');
      const resp = await fetch(`/api/exams/${pid}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return resp.json();
    }, paperId);
    const paper = detail.paper ?? detail;
    const config = paper.config ?? {};
    if (config.mode !== 'adaptive') {
      throw new Error(`难度蓝图组卷 mode 应为 adaptive，实际为 ${config.mode}`);
    }
    const mix = config.actual_mix ?? {};
    const mixSum = Object.values(mix).reduce((a, b) => a + b, 0);
    if (mixSum !== paper.question_count) {
      throw new Error(`actual_mix 之和 ${mixSum} 与题量 ${paper.question_count} 不一致（不应静默凑数）`);
    }
    // 夯实蓝图应以中等难度为主（中等题量 ≥ 易 且 ≥ 难）
    if (!((mix.medium ?? 0) >= (mix.easy ?? 0) && (mix.medium ?? 0) >= (mix.hard ?? 0))) {
      throw new Error(`夯实蓝图应中等难度最多，实际 mix=${JSON.stringify(mix)}`);
    }
    if (!paper.title.includes('自适应考卷') || !paper.title.includes('夯实')) {
      throw new Error(`标题未体现自适应/蓝图名：${paper.title}`);
    }
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${OUT}/17-blueprint-exam.png`, fullPage: true });
  });

  await step('内置评测用例开箱即用（载入内置用例 → 校验数量/来源 → 运行评测出报告）', async () => {
    await menuClick(/检\s*索\s*评\s*测/);
    await page.getByText('检索评测').first().waitFor({ timeout: 10000 });

    // 点「载入内置用例」（幂等：已存在则 created=0，仍应无报错）
    await page.getByRole('button', { name: /载\s*入\s*内\s*置\s*用\s*例/ }).click();
    await page.waitForTimeout(2500);

    // 来源标签「内置」应出现（确认来源标记渲染）；评测集表格默认分页 10 行，
    // 故「总数 ≥18」改读顶部「评测用例」统计卡（不受分页影响）
    const builtinTagVisible = await page.locator('.ant-tag', { hasText: /^内置$/ }).first().count();
    if (builtinTagVisible === 0) throw new Error('评测集未出现「内置」来源标签');
    const caseTotal = Number(
      (await page
        .locator('.ant-statistic')
        .filter({ hasText: '评测用例' })
        .locator('.ant-statistic-content-value')
        .textContent()
        .catch(() => '0')) ?? '0',
    );
    if (caseTotal < 18) {
      throw new Error(`内置评测用例不足 18 条：实际 ${caseTotal}`);
    }
    await page.screenshot({ path: `${OUT}/18-builtin-eval.png`, fullPage: true });

    // 点「运行评测」，等待「指标对比」卡片渲染图表（最多 60s）
    await page.getByRole('button', { name: /运\s*行\s*评\s*测/ }).click();
    await page
      .locator('.ant-card')
      .filter({ hasText: '指标对比' })
      .locator('canvas')
      .first()
      .waitFor({ timeout: 60000 });
    await page.waitForTimeout(1000);
  });

  await browser.close();

  console.log(report.join('\n'));
  console.log(`\n控制台错误 (${consoleErrors.length}):`);
  consoleErrors.slice(0, 10).forEach((e) => console.log('  - ' + e.slice(0, 200)));
  process.exit(report.some((r) => r.startsWith('FAIL')) ? 1 : 0);
})().catch((err) => {
  console.error('E2E 脚本异常:', err);
  process.exit(2);
});
