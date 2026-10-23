/* E2E 验证：登录 -> 知识库 -> 题库 -> 分析看板 -> 完整考试流程。
   注意：AntD Button 会在两个汉字间插入空格（如「登 录」），
   统一用 getByRole + name 正则匹配（可访问名会归一化空白）。

   运行前提：
   1. 后端 uvicorn 运行于 8000，前端 vite dev 运行于 5173
   2. 任意目录执行：npm install playwright（驱动系统 Edge，无需下载浏览器）
   3. node e2e_test.js（脚本输出截图到 docs/screenshots/） */
const { chromium } = require('playwright');
const fs = require('fs');

const BASE = 'http://localhost:5173';
const OUT = 'E:/code/traeWork/bossSayGoodForMe/interview-trainer/docs/screenshots';

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

  await step('知识库列表渲染（5 条种子资料）', async () => {
    await page.getByText('Redis 核心知识笔记').waitFor({ timeout: 10000 });
    await page.getByText('RAG 检索增强生成基础').waitFor({ timeout: 5000 });
  });

  await step('题库页渲染', async () => {
    await menuClick(/题\s*库/);
    await page.locator('table').first().waitFor({ timeout: 10000 });
    await page.waitForTimeout(1500);
  });
  await page.screenshot({ path: `${OUT}/03-questions.png` });

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

  await step('系统配置页渲染（模式展示 + LLM/Embedding 表单）', async () => {
    await menuClick(/系\s*统\s*配\s*置/);
    await page.getByText('AI 模型配置').first().waitFor({ timeout: 10000 });
    await page.getByText(/演示模式|AI 模式/).first().waitFor({ timeout: 5000 });
    await page.getByRole('button', { name: /测\s*试\s*LLM\s*连\s*接/ }).waitFor({ timeout: 5000 });
    await page.waitForTimeout(1500);
  });
  await page.screenshot({ path: `${OUT}/09-settings.png`, fullPage: true });

  await browser.close();

  console.log(report.join('\n'));
  console.log(`\n控制台错误 (${consoleErrors.length}):`);
  consoleErrors.slice(0, 10).forEach((e) => console.log('  - ' + e.slice(0, 200)));
  process.exit(report.some((r) => r.startsWith('FAIL')) ? 1 : 0);
})().catch((err) => {
  console.error('E2E 脚本异常:', err);
  process.exit(2);
});
