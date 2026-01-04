<template>
  <div style="padding: 20px; font-family: sans-serif;">
    <h1>数学题目 AI 识别调试台</h1>
    
    <div style="margin-bottom: 20px; padding: 10px; border: 1px solid #ccc; background: #f9f9f9;">
      <p><strong>状态:</strong> {{ status }}</p>
      <p v-if="error" style="color: red; font-weight: bold;">❌ 错误: {{ error }}</p>
    </div>

    <input 
      type="file" 
      ref="fileInputRef" 
      style="display: none" 
      accept="image/*,.pdf" 
      @change="onFileSelected" 
    />

    <button 
      @click="triggerSelect" 
      style="padding: 15px 30px; font-size: 18px; background-color: #4CAF50; color: white; border: none; cursor: pointer;"
      :disabled="loading"
    >
      {{ loading ? '正在上传分析中...' : '第一步：点击这里选图片' }}
    </button>

    <div v-if="result" style="margin-top: 30px; border-top: 2px solid #333; padding-top: 20px;">
      <h3>✅ 分析成功！</h3>
      
      <div style="display: flex; gap: 20px;">
        <div style="flex: 1;">
          <h4>原题图片：</h4>
          <img :src="'http://127.0.0.1:8000' + result.image_url" style="max-width: 100%; border: 1px solid #ddd;" />
        </div>

        <div style="flex: 1;">
          <h4>AI 修正文本：</h4>
          <div style="background: #eef; padding: 10px; white-space: pre-wrap;">{{ result.corrected_text }}</div>
          
          <h4>知识点标签：</h4>
          <div style="margin-top: 10px;">
            <span v-for="tag in result.knowledge_tags" :key="tag" style="background: #2196F3; color: white; padding: 5px 10px; margin-right: 5px; border-radius: 15px;">
              {{ tag }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import axios from 'axios';

// 响应式变量
const fileInputRef = ref(null);
const status = ref('等待操作...');
const error = ref('');
const result = ref(null);
const loading = ref(false);

// 1. 点击按钮 -> 触发 Input
const triggerSelect = () => {
  console.log("👉 1. 用户点击了按钮");
  status.value = "用户点击了按钮，正在打开文件选择窗口...";
  if (fileInputRef.value) {
    fileInputRef.value.click();
  } else {
    console.error("❌ 找不到 input 元素引用！");
    error.value = "代码错误：找不到 input 元素";
  }
};

// 2. 文件选好后 -> 触发 Change -> 发送请求
const onFileSelected = async (event) => {
  console.log("👉 2. 文件选择窗口关闭，检测到变化");
  const file = event.target.files[0];
  
  if (!file) {
    console.log("⚠️ 用户取消了选择");
    status.value = "用户取消了选择";
    return;
  }

  console.log(`📄 选中的文件: ${file.name}, 大小: ${file.size}`);
  
  // 开始上传流程
  loading.value = true;
  error.value = '';
  result.value = null;
  status.value = `正在上传 ${file.name} 到后端...`;

  const formData = new FormData();
  formData.append('file', file);

  try {
    console.log("🚀 3. 准备发送 Axios 请求...");
    // 确保这个 URL 跟你后端启动的地址一模一样
    const response = await axios.post('http://127.0.0.1:8000/api/v1/ocr/analyze', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });

    console.log("✅ 4. 收到后端响应:", response.data);
    status.value = "分析完成！";
    result.value = response.data;

  } catch (err) {
    console.error("❌ 请求失败:", err);
    
    if (err.code === "ERR_NETWORK") {
      error.value = "无法连接到后端！请检查：1.后端没启动？ 2.端口不是8000？";
    } else if (err.response) {
      error.value = `服务器报错 (${err.response.status}): ${JSON.stringify(err.response.data)}`;
    } else {
      error.value = `请求出错: ${err.message}`;
    }
    status.value = "发生错误";
  } finally {
    loading.value = false;
    // 清空 input，防止无法连续选同一个文件
    if (fileInputRef.value) fileInputRef.value.value = ''; 
  }
};
</script>