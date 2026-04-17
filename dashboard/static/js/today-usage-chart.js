(function(global) {
    'use strict';

    let chartInstance = null;

    function init(canvasId, colors) {
        if (chartInstance) return chartInstance;
        const canvas = document.getElementById(canvasId);
        if (!canvas || typeof Chart === 'undefined') return null;

        chartInstance = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: Array.from({ length: 24 }, (_, hour) => String(hour)),
                datasets: [
                    {
                        label: 'Sensor 1',
                        data: new Array(24).fill(null),
                        borderColor: colors.s1,
                        backgroundColor: 'rgba(253, 184, 65, 0.18)',
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.25,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    },
                    {
                        label: 'Sensor 2',
                        data: new Array(24).fill(null),
                        borderColor: colors.s2,
                        backgroundColor: 'rgba(255, 105, 180, 0.14)',
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.25,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        displayColors: true,
                        callbacks: {
                            label: (ctx) => {
                                const value = Number(ctx.parsed.y);
                                if (!Number.isFinite(value)) {
                                    return `${ctx.dataset.label}: no readings`;
                                }
                                return `${ctx.dataset.label}: ${Math.round(value * 100)}% bright`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        border: {
                            color: '#4a5568'
                        },
                        ticks: {
                            color: '#718096',
                            autoSkip: false,
                            maxRotation: 0,
                            callback: (_, index) => (index % 4 === 0 ? String(index) : '')
                        }
                    },
                    y: {
                        min: 0,
                        max: 1,
                        grid: {
                            color: 'rgba(74, 85, 104, 0.35)'
                        },
                        border: {
                            color: '#4a5568'
                        },
                        ticks: {
                            stepSize: 0.1,
                            color: '#FDB841',
                            callback: (value) => Number(value).toFixed(1)
                        }
                    }
                }
            }
        });

        return chartInstance;
    }

    function update(series1, series2, showLine1, showLine2) {
        if (!chartInstance) return;
        chartInstance.data.labels = Array.from({ length: 24 }, (_, hour) => String(hour));
        chartInstance.data.datasets[0].data = showLine1 ? series1 : new Array(24).fill(null);
        chartInstance.data.datasets[1].data = showLine2 ? series2 : new Array(24).fill(null);
        chartInstance.update();
    }

    global.TodayUsageChartHelper = {
        init,
        update
    };
})(window);
