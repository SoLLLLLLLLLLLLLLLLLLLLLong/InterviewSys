<template>
  <!-- 后台图表卡片：封装 ECharts，让管理员/面试官后台可以复用柱状图、折线图、饼图。 -->
  <article class="platform-card chart-card">
    <div class="platform-card-heading">
      <h3>{{ title }}</h3>
      <span>{{ subtitle }}</span>
    </div>
    <!-- ref="chartRef" 用来拿到真实 DOM，ECharts 必须挂载到一个 DOM 容器上。 -->
    <div v-if="hasData" ref="chartRef" class="chart-canvas"></div>
    <div v-else class="platform-empty chart-empty">{{ emptyText }}</div>
  </article>
</template>

<script setup>
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  // title/subtitle 负责卡片标题文案。
  title: { type: String, required: true },
  subtitle: { type: String, default: "" },
  // type 控制图表类型：bar / line / pie。
  type: { type: String, default: "bar" },
  // data 由后端统计接口返回，前端只负责映射成 ECharts option。
  data: { type: Array, default: () => [] },
  emptyText: { type: String, default: "暂无可视化数据。" },
});

const chartRef = ref(null);
let chart = null;

// computed 判断是否有可画的数据，没有数据就展示空状态，避免空白图表让用户误解。
const hasData = computed(() => props.data.some((item) => Number(item.value ?? item.score ?? item.latency_ms ?? 0) > 0));

// buildOption 是 ECharts 的核心配置函数。
// 面试可以说：我把后端数据转换成 option，再调用 chart.setOption 渲染。
function buildOption() {
  const textColor = "#38516c";
  if (props.type === "pie") {
    return {
      tooltip: { trigger: "item" },
      color: ["#2f8fe8", "#75c6a7", "#f0a35a", "#e56f63", "#8b9cff"],
      series: [
        {
          type: "pie",
          radius: ["48%", "72%"],
          data: props.data,
          label: { color: textColor },
        },
      ],
    };
  }
  if (props.type === "line") {
    return {
      tooltip: { trigger: "axis" },
      grid: { left: 34, right: 20, top: 24, bottom: 30 },
      xAxis: { type: "category", data: props.data.map((item) => item.label || item.name), axisLabel: { color: textColor } },
      yAxis: { type: "value", axisLabel: { color: textColor } },
      series: [
        {
          type: "line",
          smooth: true,
          symbolSize: 7,
          areaStyle: { opacity: 0.14 },
          lineStyle: { width: 3 },
          data: props.data.map((item) => item.score ?? item.latency_ms ?? item.value ?? 0),
          color: "#2f8fe8",
        },
      ],
    };
  }
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 34, right: 20, top: 24, bottom: 30 },
    xAxis: { type: "category", data: props.data.map((item) => item.name || item.label), axisLabel: { color: textColor } },
    yAxis: { type: "value", axisLabel: { color: textColor } },
    series: [
      {
        type: "bar",
        barWidth: 22,
        data: props.data.map((item) => item.value ?? item.score ?? 0),
        itemStyle: { borderRadius: [9, 9, 2, 2], color: "#2f8fe8" },
      },
    ],
  };
}

function renderChart() {
  // DOM 不存在或没有数据时不初始化图表，避免 ECharts 报错。
  if (!chartRef.value || !hasData.value) return;
  // ||= 表示 chart 没有初始化时才执行 echarts.init，避免重复创建实例。
  chart ||= echarts.init(chartRef.value);
  chart.setOption(buildOption(), true);
}

// 数据变化后重新渲染图表。nextTick 用来等待 Vue 先把 DOM 更新完。
watch(() => [props.type, props.data], () => nextTick(renderChart), { deep: true });

onMounted(() => {
  // mounted 阶段 DOM 已经挂载完成，适合初始化第三方图表库。
  nextTick(renderChart);
  // 窗口大小变化时重新 resize，保证图表自适应布局。
  window.addEventListener("resize", renderChart);
});

onBeforeUnmount(() => {
  // 组件销毁前清理事件监听和图表实例，避免内存泄漏。
  window.removeEventListener("resize", renderChart);
  chart?.dispose();
  chart = null;
});
</script>
