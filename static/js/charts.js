// charts.js

// Theme management
function toggleTheme() {
  const html = document.documentElement;
  const currentTheme = html.getAttribute("data-theme");
  const newTheme = currentTheme === "dark" ? "light" : "dark";
  html.setAttribute("data-theme", newTheme);
  localStorage.setItem("theme", newTheme);
  updateChartsTheme(newTheme);
}

function initTheme() {
  const savedTheme = localStorage.getItem("theme") || "light";
  document.documentElement.setAttribute("data-theme", savedTheme);
  updateChartsTheme(savedTheme);
}

function updateChartsTheme(theme) {
  const chartBg = theme === "dark" ? "#343a40" : "#ffffff";
  const chartText = theme === "dark" ? "#f8f9fa" : "#212529";
  const updateLayout = {
    paper_bgcolor: chartBg,
    plot_bgcolor: chartBg,
    font: { color: chartText },
  };

  if (typeof Plotly !== "undefined") {
    Plotly.relayout("comparison-chart1", updateLayout);
    Plotly.relayout("comparison-chart2", updateLayout);
  }
}

// Chart configuration
const chartConfig = {
  responsive: true,
  displayModeBar: false,
  toImageButtonOptions: {
    format: "png",
    filename: "chart",
    height: null,
    width: null,
  },
};

// Initialize charts if on results page
function initCharts(chartData1, chartData2) {
  if (!chartData1 || !chartData2) return;

  const theme = document.documentElement.getAttribute("data-theme");
  const chartBg = theme === "dark" ? "#343a40" : "#ffffff";
  const chartText = theme === "dark" ? "#f8f9fa" : "#212529";

  chartData1.layout = {
    title: "Investment Returns Comparison",
    barmode: "group",
    yaxis: { title: "Amount (₹)" },
    paper_bgcolor: chartBg,
    plot_bgcolor: chartBg,
    font: { color: chartText },
    autosize: true,
    margin: {
      l: 50,
      r: 20,
      b: 50,
      t: 50,
      pad: 4,
    },
  };

  chartData2.layout = {
    title: "Year-wise Growth Comparison",
    xaxis: { title: "Year" },
    yaxis: { title: "Amount (₹)" },
    paper_bgcolor: chartBg,
    plot_bgcolor: chartBg,
    font: { color: chartText },
    autosize: true,
    margin: {
      l: 50,
      r: 20,
      b: 50,
      t: 50,
      pad: 4,
    },
  };

  Plotly.newPlot(
    "comparison-chart1",
    chartData1.data,
    chartData1.layout,
    chartConfig
  );
  Plotly.newPlot(
    "comparison-chart2",
    chartData2.data,
    chartData2.layout,
    chartConfig
  );
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  initTheme();

  // Only initialize charts if we're on the results page
  if (typeof chartData1 !== "undefined" && typeof chartData2 !== "undefined") {
    initCharts(chartData1, chartData2);
  }
});
