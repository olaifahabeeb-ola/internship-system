/*
 * InternTrack — Shared Chart.js helpers
 * Chart.js is loaded via CDN in base.html.
 * This file contains reusable chart factory functions.
 */

/**
 * Create a simple bar chart.
 * @param {string} canvasId - The canvas element id
 * @param {string[]} labels  - X-axis labels
 * @param {number[]} data    - Y-axis data
 * @param {string} colour    - Bar colour (hex or CSS colour)
 */
function makeBarChart(canvasId, labels, data, colour = 'rgba(13,110,253,0.75)') {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: colour,
                borderRadius: 4,
                borderSkipped: false,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
        }
    });
}

/**
 * Create a doughnut chart.
 */
function makeDoughnutChart(canvasId, labels, data, colours) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{ data, backgroundColor: colours, borderWidth: 2 }]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'bottom', labels: { font: { size: 11 } } } }
        }
    });
}
