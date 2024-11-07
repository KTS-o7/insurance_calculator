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

// Chart configuration
const chartConfig = {
  responsive: true,
  displayModeBar: false,
  toImageButtonOptions: {
    format: "svg",
    filename: "chart",
    height: null,
    width: null,
  },
};

function initCharts(chartData1, chartData2) {
  const chartConfig = {
    responsive: true,
    displayModeBar: false,
  };

  try {
    // Create charts first
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
    console.log("Charts initialized");
    return true;
  } catch (error) {
    console.error("Error initializing charts:", error);
    return false;
  }
}

function updateChartsTheme(isDark) {
  // Check if chart elements exist first
  const chart1 = document.getElementById("comparison-chart1");
  const chart2 = document.getElementById("comparison-chart2");
  isDark = isDark === "dark";
  if (!chart1 || !chart2) return;

  Plotly.relayout("comparison-chart1", {
    paper_bgcolor: isDark ? "#333" : "#fff",
    plot_bgcolor: isDark ? "#333" : "#fff",
    font: { color: isDark ? "#fff" : "#000" },
  });
  Plotly.relayout("comparison-chart2", {
    paper_bgcolor: isDark ? "#333" : "#fff",
    plot_bgcolor: isDark ? "#333" : "#fff",
    font: { color: isDark ? "#fff" : "#000" },
  });
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  // Initialize charts first if data exists
  if (typeof chartData1 !== "undefined" && typeof chartData2 !== "undefined") {
    const chartsInitialized = initCharts(chartData1, chartData2);
    if (chartsInitialized) {
      initTheme(); // Only initialize theme after charts are ready
    }
  }
});
