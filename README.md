# 🦋 Firefly-skill

**A [Claude Code](https://claude.com/claude-code) skill that runs your LinkedIn job hunt for you: scrape, filter, and export a ranked shortlist. Fully automated, read-only.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) ![version](https://img.shields.io/badge/version-1.0.0-brightgreen)

<p align="center">
  <img src="FIREFLY.jpg" alt="Firefly" width="360">
  <br>
  <sub>Artwork © <b>@degrees_25</b> — all rights reserved.</sub>
</p>

---

## The grind it kills

Hunting for jobs on LinkedIn is hours of the same loop. Search a title. Open a posting. Squint at the fine print to see if it really wants 5 years. Check whether it is actually in your city. Try to remember if you already applied. Copy it into a spreadsheet. Do it again for the next one, and again next week.

Firefly does that whole loop while you do something else.

## What it does

- **Reads every job's full description.** It clicks "see more" on each posting, so the years-of-experience and location filters are based on the real text, not a truncated preview.
- **Throws out the time-wasters.** Roles asking for more years than you have, jobs outside your target location, disguised direct-sales / MLM postings, and anything you already applied to. It remembers past runs, so the same job never shows up twice.
- **Ranks by fit.** It scores each role against your background and writes a clean Excel workbook, sorted best-match first, with three tabs: the full job list, a fit ranking with "why it fits / watch-outs", and a summary.
- **Never touches your account.** Read-only by design. It browses, it does not apply, so it will not trip captchas or do anything risky. Applying is a separate job.
- **Runs hands-off.** Kick it off when you want, or put it on a schedule and let new matches pile up.

In a head-to-head benchmark, Firefly produced correct, complete shortlists **94.5%** of the time, versus **66.7%** for a capable general agent with no skill.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- [browser-act](https://github.com/browser-act/skills) for logged-in browsing
- Python 3.12+ with [uv](https://github.com/astral-sh/uv)

## Install

Tell your agent:

> Install the Firefly-skill from https://github.com/EclairAikome/Firefly-skill and verify it works.

Then open `config.yaml`, set your search queries, location, and filters, and say **"do a job-hunt run"**.

## License

MIT. See [LICENSE](LICENSE).

---
---

# 🦋 Firefly-skill

**一个帮你自动跑 LinkedIn 求职的 [Claude Code](https://claude.com/claude-code) skill：搜索、筛选、导出一份按匹配度排好序的清单。全自动，只读不投递。**

## 它替你干掉的苦差事

在 LinkedIn 找工作就是不停重复同一套动作。搜一个职位，点开一条岗位，眯着眼看它是不是真要五年经验，确认是不是在你所在的城市，再回忆自己是不是已经投过，然后抄进表格。下一条再来一遍，下周再来一遍。

这一整套，Firefly 替你跑，你去忙别的。

## 它做什么

- **读每个岗位的完整 JD。** 它会点开每条岗位的"see more"，所以经验年限和地点的筛选依据的是全文，而不是被截断的预览。
- **扔掉浪费时间的。** 要求年限超过你的、不在目标城市的、伪装成营销的直销/拉人头岗、以及你已经投过的。它记得历次跑过的结果，同一个岗位不会出现第二次。
- **按匹配度排序。** 它把每个岗位对照你的背景打分，导出一份干净的 Excel，最匹配的排在最前，含三个子表：完整岗位清单、带"为什么适合/注意点"的匹配排名、以及汇总。
- **绝不碰你的账号。** 设计上就是只读。它只浏览，不投递，所以不会触发验证码、不会做任何有风险的操作。投递是另一回事。
- **省心。** 想跑就跑，或挂上定时任务，让新匹配自己攒着。

实测对比：Firefly 产出正确完整清单的比例是 **94.5%**，而一个能干的、没有这个 skill 的通用 agent 只有 **66.7%**。

## 依赖

- [Claude Code](https://claude.com/claude-code)
- [browser-act](https://github.com/browser-act/skills)（带登录态浏览）
- Python 3.12+ 和 [uv](https://github.com/astral-sh/uv)

## 安装

对你的 agent 说：

> Install the Firefly-skill from https://github.com/EclairAikome/Firefly-skill and verify it works.

然后打开 `config.yaml`，填上你的搜索关键词、地点和筛选条件，再说一句**"do a job-hunt run"**。

## 许可证

MIT，见 [LICENSE](LICENSE)。
