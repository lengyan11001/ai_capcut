<template>
  <div class="app-root">
    <header class="top-bar">
      <div class="brand">七猫风格演示</div>
      <input v-model="keyword" class="search" placeholder="搜书名/作者" />
    </header>

    <main class="content">
      <section v-if="activeTab === 'home'">
        <div class="section-title">热门推荐</div>
        <div class="book-grid">
          <div v-for="book in filteredBooks" :key="book.id" class="book-card" @click="openBook(book)">
            <div class="cover">{{ book.coverText }}</div>
            <div class="name">{{ book.title }}</div>
            <div class="meta">{{ book.author }} · {{ book.category }}</div>
            <button class="ghost-btn" @click.stop="addShelf(book)">加入书架</button>
          </div>
        </div>

        <div class="section-title">畅销榜</div>
        <div class="rank-list">
          <div v-for="(book, idx) in ranking" :key="book.id" class="rank-item" @click="openBook(book)">
            <span class="rank-no">{{ idx + 1 }}</span>
            <span class="rank-name">{{ book.title }}</span>
          </div>
        </div>
      </section>

      <section v-if="activeTab === 'shelf'">
        <div class="section-title">我的书架（{{ shelf.length }}）</div>
        <div v-if="shelf.length === 0" class="empty">书架空空的，去书城加几本吧</div>
        <div v-for="book in shelf" :key="book.id" class="shelf-item">
          <div>
            <div class="name">{{ book.title }}</div>
            <div class="meta">上次阅读：{{ progressMap[book.id] || "未开始" }}</div>
          </div>
          <div class="actions">
            <button class="ghost-btn" @click="openBook(book)">继续阅读</button>
            <button class="ghost-btn danger" @click="removeShelf(book.id)">移除</button>
          </div>
        </div>
      </section>

      <section v-if="activeTab === 'me'">
        <div class="profile-card">
          <div class="avatar">书</div>
          <div>
            <div class="name">演示用户</div>
            <div class="meta">余额：{{ coins }} 书币（假数据）</div>
          </div>
        </div>
        <div class="section-title">分类</div>
        <div class="tags">
          <span v-for="tag in categories" :key="tag" class="tag">{{ tag }}</span>
        </div>
      </section>
    </main>

    <div v-if="currentBook" class="reader-mask">
      <div class="reader">
        <div class="reader-header">
          <div class="name">{{ currentBook.title }}</div>
          <button class="ghost-btn" @click="closeReader">关闭</button>
        </div>
        <div class="reader-chapter">{{ currentChapter.title }}</div>
        <div class="reader-content">{{ currentChapter.content }}</div>
        <div class="reader-footer">
          <button class="ghost-btn" :disabled="chapterIndex <= 0" @click="prevChapter">上一章</button>
          <button class="ghost-btn" :disabled="chapterIndex >= currentBook.chapters.length - 1" @click="nextChapter">下一章</button>
        </div>
      </div>
    </div>

    <nav class="tabbar">
      <button :class="['tab', activeTab === 'home' && 'active']" @click="activeTab = 'home'">书城</button>
      <button :class="['tab', activeTab === 'shelf' && 'active']" @click="activeTab = 'shelf'">书架</button>
      <button :class="['tab', activeTab === 'me' && 'active']" @click="activeTab = 'me'">我的</button>
    </nav>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

const categories = ["玄幻", "都市", "悬疑", "言情", "历史", "科幻"];
const coins = ref(8888);
const keyword = ref("");
const activeTab = ref("home");
const chapterIndex = ref(0);
const currentBook = ref(null);
const progressMap = ref(loadJSON("demo_progress", {}));
const shelf = ref(loadJSON("demo_shelf", []));

const books = ref([
  makeBook("b1", "我在都市修长生", "青山客", "都市", "都"),
  makeBook("b2", "万古第一剑神", "墨海行舟", "玄幻", "玄"),
  makeBook("b3", "诡案追凶实录", "夜行笔记", "悬疑", "悬"),
  makeBook("b4", "她在星海等你", "南风知意", "言情", "言"),
  makeBook("b5", "大唐第一权臣", "云中客", "历史", "史"),
  makeBook("b6", "群星尽头", "深空旅人", "科幻", "科")
]);

const filteredBooks = computed(() => {
  const q = keyword.value.trim();
  if (!q) return books.value;
  return books.value.filter((b) => b.title.includes(q) || b.author.includes(q));
});

const ranking = computed(() => books.value.slice(0, 5));
const currentChapter = computed(() => {
  if (!currentBook.value) return { title: "", content: "" };
  return currentBook.value.chapters[chapterIndex.value];
});

function makeBook(id, title, author, category, coverText) {
  return {
    id,
    title,
    author,
    category,
    coverText,
    chapters: [
      { title: "第一章 初入江湖", content: "这是演示章节内容。主角在一个清晨醒来，决定改变命运。" },
      { title: "第二章 风云将起", content: "江湖并不平静，各方势力暗流涌动，新的故事即将开始。" },
      { title: "第三章 一鸣惊人", content: "经历一场试炼后，主角终于崭露头角，前路更广阔。" }
    ]
  };
}

function addShelf(book) {
  if (shelf.value.some((b) => b.id === book.id)) return;
  shelf.value.unshift(book);
  saveJSON("demo_shelf", shelf.value);
}

function removeShelf(bookId) {
  shelf.value = shelf.value.filter((b) => b.id !== bookId);
  saveJSON("demo_shelf", shelf.value);
}

function openBook(book) {
  currentBook.value = book;
  chapterIndex.value = 0;
  markProgress();
}

function closeReader() {
  currentBook.value = null;
}

function prevChapter() {
  if (chapterIndex.value <= 0) return;
  chapterIndex.value -= 1;
  markProgress();
}

function nextChapter() {
  if (!currentBook.value || chapterIndex.value >= currentBook.value.chapters.length - 1) return;
  chapterIndex.value += 1;
  markProgress();
}

function markProgress() {
  if (!currentBook.value) return;
  progressMap.value[currentBook.value.id] = currentChapter.value.title;
  saveJSON("demo_progress", progressMap.value);
}

function loadJSON(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function saveJSON(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore demo persistence error
  }
}
</script>

<style>
* {
  box-sizing: border-box;
}
.app-root {
  min-height: 100vh;
  background: #f6f7fb;
  color: #222;
  font-family: Arial, sans-serif;
  padding-bottom: 72px;
}
.top-bar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 14px 16px;
  background: #ffffff;
  border-bottom: 1px solid #eee;
}
.brand {
  font-weight: 700;
  color: #ff5a3d;
}
.search {
  flex: 1;
  border: 1px solid #ddd;
  border-radius: 20px;
  padding: 8px 12px;
}
.content {
  padding: 12px 14px 24px;
}
.section-title {
  margin: 14px 0 10px;
  font-size: 18px;
  font-weight: 700;
}
.book-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.book-card {
  background: #fff;
  border-radius: 12px;
  padding: 10px;
}
.cover {
  height: 72px;
  border-radius: 10px;
  background: linear-gradient(135deg, #ff8f70, #ff5a3d);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  margin-bottom: 8px;
}
.name {
  font-size: 16px;
  font-weight: 700;
}
.meta {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}
.ghost-btn {
  margin-top: 8px;
  border: 1px solid #ff5a3d;
  color: #ff5a3d;
  background: #fff;
  border-radius: 14px;
  padding: 6px 10px;
}
.ghost-btn.danger {
  border-color: #ef4444;
  color: #ef4444;
}
.rank-list,
.shelf-item,
.profile-card {
  background: #fff;
  border-radius: 12px;
  padding: 10px 12px;
}
.rank-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px dashed #eee;
}
.rank-item:last-child {
  border-bottom: none;
}
.rank-no {
  width: 20px;
  text-align: center;
  color: #ff5a3d;
  font-weight: 700;
}
.shelf-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.actions {
  display: flex;
  gap: 8px;
}
.empty {
  color: #777;
  font-size: 14px;
  padding: 18px 0;
}
.profile-card {
  display: flex;
  gap: 12px;
  align-items: center;
}
.avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #ffefe8;
  color: #ff5a3d;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tag {
  background: #fff;
  border: 1px solid #eee;
  border-radius: 16px;
  padding: 6px 10px;
  font-size: 13px;
}
.tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  background: #fff;
  border-top: 1px solid #eee;
}
.tab {
  border: none;
  background: transparent;
  padding: 12px 0;
  font-size: 14px;
  color: #666;
}
.tab.active {
  color: #ff5a3d;
  font-weight: 700;
}
.reader-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: end;
}
.reader {
  width: 100%;
  max-height: 85vh;
  background: #fffaf2;
  border-top-left-radius: 16px;
  border-top-right-radius: 16px;
  padding: 14px;
  overflow: auto;
}
.reader-header,
.reader-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.reader-chapter {
  margin: 12px 0 8px;
  font-weight: 700;
}
.reader-content {
  line-height: 1.8;
  color: #444;
}
</style>
