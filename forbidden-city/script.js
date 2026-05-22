const story = document.querySelector(".scroll-story");
const stage = document.querySelector(".sticky-stage");
const timeGrid = document.querySelector("#timeGrid");
const timeDetail = document.querySelector("#timeDetail");
const artifactButtons = document.querySelectorAll(".artifact");
const artifactDetail = document.querySelector("#artifactDetail");
const soundToggle = document.querySelector(".sound-toggle");
const sceneTitle = document.querySelector("#sceneTitle");
const sceneCopy = document.querySelector("#sceneCopy");
const prevScene = document.querySelector("#prevScene");
const nextScene = document.querySelector("#nextScene");

const times = [
  {
    name: "卯时",
    hour: "05:00",
    title: "午门晨启",
    short: "午门晨启，先看宫城尺度",
    copy: "城门与阙楼迎来第一束光，宫城的尺度从这里展开。",
    detail: "从午门进入，视线先被高大的城台和两翼阙楼收束。这里是紫禁城南端最有仪式感的起点，适合先建立宫城的方向、轴线和尺度感。"
  },
  {
    name: "辰时",
    hour: "07:00",
    title: "金水桥影",
    short: "金水桥影，理解礼制路径",
    copy: "五座石桥跨过内金水河，礼制秩序藏在路径与方位里。",
    detail: "内金水河从广场前蜿蜒穿过，桥的数量、位置和通行等级都有讲究。走到这里，可以把建筑空间当作一张礼仪地图来读。"
  },
  {
    name: "巳时",
    hour: "09:00",
    title: "太和朝仪",
    short: "太和朝仪，进入三大殿",
    copy: "三大殿层层抬升，太和殿是紫禁城最庄严的中心。",
    detail: "太和殿承载国家大典，台基、丹陛、屋顶和广场共同放大了仪式的威严。这里最适合观察故宫建筑如何用高度和距离制造秩序。"
  },
  {
    name: "午时",
    hour: "11:00",
    title: "中轴日正",
    short: "中轴日正，观察屋顶与脊兽",
    copy: "日光落在丹陛与脊兽上，建筑语言显出皇城的分寸。",
    detail: "午时的光线最利于观察屋顶等级、脊兽数量、彩画与台阶。把这些细节连起来，就能看见宫殿等级如何被写进建筑表面。"
  },
  {
    name: "未时",
    hour: "13:00",
    title: "乾清日影",
    short: "乾清日影，转向内廷生活",
    copy: "前朝转入内廷，乾清宫见证政务、家国与日常交织。",
    detail: "过了乾清门，空间从外朝的大尺度转向内廷。乾清宫既关乎政务，也连着帝王生活，是理解紫禁城从公共礼制转入私人秩序的关键。"
  },
  {
    name: "申时",
    hour: "15:00",
    title: "交泰印信",
    short: "交泰印信，器物连接制度",
    copy: "印玺、册宝与空间秩序，让制度化为可触的器物。",
    detail: "交泰殿位于乾清宫与坤宁宫之间，象征内廷秩序的转换。以印玺、陈设和匾额为线索，可以把抽象制度落到具体器物上。"
  },
  {
    name: "酉时",
    hour: "17:00",
    title: "御园风起",
    short: "御园风起，在园林里慢下来",
    copy: "亭台、古柏与叠石收束宫城节奏，留出一段清雅。",
    detail: "御花园让宫城的节奏忽然变轻。亭台、叠石、古树与花木把威严的轴线转化为可以停留的园林经验。"
  },
  {
    name: "戌时",
    hour: "19:00",
    title: "神武暮鼓",
    short: "神武暮鼓，从北门收束行程",
    copy: "暮色从北门合拢，宫城在夜色中回到沉静。",
    detail: "从神武门回望，整条中轴线被压缩成一天的记忆。这里适合收束路线，也适合把建筑、器物和时间重新串起来。"
  }
];

const artifacts = {
  bronze: {
    title: "青铜礼器",
    copy:
      "礼器不只是陈列品，它们定义了祭祀、宴飨和身份秩序。把纹样、铭文与使用场景连起来看，宫廷收藏就从“古物”变成了一套可读的制度语言。"
  },
  ceramic: {
    title: "御窑瓷器",
    copy:
      "釉色、器形与年款记录了技术和审美的高峰。青花、斗彩、珐琅彩之间的差异，正好能看见宫廷趣味如何影响工艺体系。"
  },
  clock: {
    title: "宫廷钟表",
    copy:
      "清宫钟表连接了机械、外交与娱乐。它们以报时为功能，也以复杂联动、音乐和装饰展示新的世界经验。"
  },
  painting: {
    title: "书画长卷",
    copy:
      "长卷适合慢读。观者沿着画面移动，时间、空间和叙事一同展开，这也正是本页采用横向长卷交互的原因。"
  }
};

let activeScene = 0;

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function sceneTarget(index) {
  return story.offsetTop + ((story.offsetHeight - window.innerHeight) * index) / (times.length - 1);
}

function setActiveScene(index, shouldScroll = false) {
  activeScene = clamp(index, 0, times.length - 1);
  const item = times[activeScene];

  sceneTitle.textContent = item.title;
  sceneCopy.textContent = item.detail;

  document.querySelectorAll(".scene-card").forEach((card, cardIndex) => {
    card.classList.toggle("active", cardIndex === activeScene);
  });

  timeGrid.querySelectorAll(".time-item").forEach((button, buttonIndex) => {
    button.classList.toggle("active", buttonIndex === activeScene);
  });

  renderTimeDetail(activeScene);

  if (shouldScroll) {
    window.scrollTo({ top: sceneTarget(activeScene), behavior: "smooth" });
  }
}

function updateScroll() {
  const rect = story.getBoundingClientRect();
  const scrollable = story.offsetHeight - window.innerHeight;
  const progress = clamp(-rect.top / scrollable, 0, 1);
  const art = document.querySelector(".scroll-art");
  const travel = Math.max(0, art.offsetWidth - window.innerWidth);
  const panX = -travel * progress;
  const nextIndex = Math.round(progress * (times.length - 1));

  stage.style.setProperty("--story-progress", progress.toFixed(4));
  stage.style.setProperty("--pan-x", `${panX}px`);

  if (nextIndex !== activeScene && rect.top <= 0 && rect.bottom >= window.innerHeight) {
    setActiveScene(nextIndex);
  }
}

function renderTimes() {
  timeGrid.innerHTML = times
    .map(
      (item, index) => `
        <button class="time-item${index === 0 ? " active" : ""}" type="button" data-index="${index}">
          <strong>${item.name}</strong>
          <span>${item.hour}</span>
          <p>${item.short}</p>
        </button>
      `
    )
    .join("");

  timeGrid.querySelectorAll(".time-item").forEach((button) => {
    button.addEventListener("click", () => {
      setActiveScene(Number(button.dataset.index));
    });
  });
}

function renderTimeDetail(index) {
  const item = times[index];
  timeDetail.classList.remove("is-changing");
  void timeDetail.offsetWidth;
  timeDetail.classList.add("is-changing");
  timeDetail.innerHTML = `
    <div>
      <strong>${item.hour} · ${item.name}</strong>
      <h3>${item.title}</h3>
    </div>
    <p>${item.detail}</p>
    <button class="jump-button" type="button">定位到长卷</button>
  `;

  timeDetail.querySelector(".jump-button").addEventListener("click", () => {
    setActiveScene(index, true);
  });
}

function renderArtifact(key) {
  const item = artifacts[key];
  artifactDetail.innerHTML = `<h3>${item.title}</h3><p>${item.copy}</p>`;
}

document.querySelectorAll(".scene-card").forEach((card, index) => {
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.setAttribute("aria-label", `查看${times[index].title}`);
  card.addEventListener("click", () => setActiveScene(index));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setActiveScene(index);
    }
  });
});

prevScene.addEventListener("click", () => setActiveScene(activeScene - 1, true));
nextScene.addEventListener("click", () => setActiveScene(activeScene + 1, true));

artifactButtons.forEach((button) => {
  button.addEventListener("click", () => {
    artifactButtons.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    renderArtifact(button.dataset.artifact);
  });
});

soundToggle.addEventListener("click", () => {
  const pressed = soundToggle.getAttribute("aria-pressed") === "true";
  soundToggle.setAttribute("aria-pressed", String(!pressed));
  soundToggle.querySelector(".sound-label").textContent = pressed ? "静音" : "风声";
});

renderTimes();
renderTimeDetail(0);
renderArtifact("bronze");
setActiveScene(0);
updateScroll();

window.addEventListener("scroll", updateScroll, { passive: true });
window.addEventListener("resize", updateScroll);
