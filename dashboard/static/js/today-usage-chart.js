(function(global) {
    'use strict';

    let chartInstance = null;
    const GRAPH_MAX_LUX = 20000;
    const BUCKETS_PER_HOUR = 12;
    const POINTS_PER_DAY = 24 * BUCKETS_PER_HOUR;

    function makeDayLabels() {
        return Array.from({ length: POINTS_PER_DAY }, (_, idx) => {
            const hour = Math.floor(idx / BUCKETS_PER_HOUR);
            const minute = (idx % BUCKETS_PER_HOUR) * 5;
            return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
        });
    }

    function init(canvasId, colors) {
        if (chartInstance) return chartInstance;
        const canvas = document.getElementById(canvasId);
        if (!canvas || typeof Chart === 'undefined') return null;

        chartInstance = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: makeDayLabels(),
                datasets: [
                    {
                        label: 'Sensor 1',
                        data: new Array(POINTS_PER_DAY).fill(null),
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
                        data: new Array(POINTS_PER_DAY).fill(null),
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
                layout: {
                    padding: { left: 0, right: 0, top: 2, bottom: 0 }
                },
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
                            title: (items) => {
                                if (!items || !items.length) return '';
                                return `Time: ${items[0].label}`;
                            },
                            label: (ctx) => {
                                const value = Number(ctx.parsed.y);
                                if (!Number.isFinite(value)) {
                                    return `${ctx.dataset.label}: no readings`;
                                }
                                return `${ctx.dataset.label}: ${Math.round(value)} lux`;
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
                            padding: 2,
                            callback: (_, index) => (index % (BUCKETS_PER_HOUR * 4) === 0 ? String(index / BUCKETS_PER_HOUR) : '')
                        }
                    },
                    y: {
                        min: 0,
                        max: GRAPH_MAX_LUX,
                        grid: {
                            color: 'rgba(74, 85, 104, 0.35)'
                        },
                        border: {
                            color: '#4a5568'
                        },
                        ticks: {
                            stepSize: 2000,
                            color: '#FDB841',
                            callback: (value) => `${Math.round(Number(value))}`
                        }
                    }
                }
            }
        });

        const wrapper = canvas.closest('.graph-canvas-wrapper');
        if (wrapper && typeof ResizeObserver !== 'undefined') {
            const ro = new ResizeObserver(() => {
                if (chartInstance) {
                    chartInstance.resize();
                }
            });
            ro.observe(wrapper);
        }
        requestAnimationFrame(() => {
            if (chartInstance) {
                chartInstance.resize();
            }
        });

        return chartInstance;
    }

    function update(series1, series2, showLine1, showLine2) {
        if (!chartInstance) return;
        const toLux = (series) => (series || []).map((v) => {
            const n = Number(v);
            return Number.isFinite(n) ? Math.max(0, Math.min(1, n)) * GRAPH_MAX_LUX : null;
        });
        const s1Lux = toLux(series1);
        const s2Lux = toLux(series2);
        chartInstance.data.labels = makeDayLabels();
        chartInstance.data.datasets[0].data = showLine1 ? s1Lux : new Array(POINTS_PER_DAY).fill(null);
        chartInstance.data.datasets[1].data = showLine2 ? s2Lux : new Array(POINTS_PER_DAY).fill(null);
        chartInstance.update();
    }

    global.TodayUsageChartHelper = {
        init,
        update
    };
})(window);
