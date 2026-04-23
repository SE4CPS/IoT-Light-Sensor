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
                        backgroundColor: 'rgba(253, 184, 65, 0.16)',
                        borderWidth: 2.8,
                        fill: true,
                        cubicInterpolationMode: 'monotone',
                        tension: 0.72,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    },
                    {
                        label: 'Sensor 2',
                        data: new Array(POINTS_PER_DAY).fill(null),
                        borderColor: colors.s2,
                        backgroundColor: 'rgba(255, 105, 180, 0.14)',
                        borderWidth: 2.8,
                        fill: true,
                        cubicInterpolationMode: 'monotone',
                        tension: 0.72,
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
                                const rawSeries = ctx.dataset && ctx.dataset.rawLuxSeries;
                                const rawValue = rawSeries && Number.isFinite(Number(rawSeries[ctx.dataIndex]))
                                    ? Number(rawSeries[ctx.dataIndex])
                                    : NaN;
                                if (!Number.isFinite(rawValue)) {
                                    return `${ctx.dataset.label}: no readings`;
                                }
                                return `${ctx.dataset.label}: ${Math.round(rawValue)} lux`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Hours',
                            color: '#a0aec0',
                            font: { size: 12, weight: '600' },
                            padding: { top: 6 }
                        },
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
                        title: {
                            display: true,
                            text: 'Lux_Range',
                            color: '#a0aec0',
                            font: { size: 12, weight: '600' },
                            padding: { bottom: 8 }
                        },
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

    function smoothLuxSeries(series) {
        const vals = (series || []).map((v) => {
            const n = Number(v);
            return Number.isFinite(n) ? Math.max(0, Math.min(GRAPH_MAX_LUX, n)) : null;
        });
        if (!vals.length) return vals;

        // Median filter to suppress isolated spikes.
        const medianFiltered = vals.map((v, i) => {
            if (v === null) return null;
            const neighborhood = [];
            for (let k = i - 2; k <= i + 2; k++) {
                if (k < 0 || k >= vals.length) continue;
                const n = vals[k];
                if (n !== null) neighborhood.push(n);
            }
            if (!neighborhood.length) return v;
            neighborhood.sort((a, b) => a - b);
            return neighborhood[Math.floor(neighborhood.length / 2)];
        });

        // Hard suppress one-point/two-point spikes before smoothing.
        const despiked = medianFiltered.map((v, i) => {
            if (v === null) return null;
            const left = i > 0 ? medianFiltered[i - 1] : null;
            const right = i < medianFiltered.length - 1 ? medianFiltered[i + 1] : null;
            if (left === null || right === null) return v;
            const localBase = (left + right) / 2;
            if (localBase <= 0) return v;
            // If current value is an abrupt spike >2.6x local baseline, pull it down.
            if (v > localBase * 2.6) {
                return localBase * 1.35;
            }
            return v;
        });

        // Wide Gaussian-like smoothing pass for broad wave profile.
        const kernel = [1, 2, 3, 4, 5, 4, 3, 2, 1];
        const center = Math.floor(kernel.length / 2);
        const smoothOnce = (arr) => arr.map((v, i) => {
            if (v === null) return null;
            let acc = 0;
            let wsum = 0;
            for (let k = 0; k < kernel.length; k++) {
                const j = i + (k - center);
                if (j < 0 || j >= arr.length) continue;
                const n = arr[j];
                if (n === null) continue;
                const w = kernel[k];
                acc += n * w;
                wsum += w;
            }
            const out = wsum > 0 ? acc / wsum : v;
            return Math.max(0, Math.min(GRAPH_MAX_LUX, out));
        });

        // Two smoothing passes to remove sharp triangles.
        return smoothOnce(smoothOnce(despiked));
    }

    function shapeWaveFromLux(series, onMask) {
        const vals = (series || []).map((v) => {
            const n = Number(v);
            return Number.isFinite(n) ? Math.max(0, Math.min(GRAPH_MAX_LUX, n)) : null;
        });
        if (!vals.length) return vals;
        const out = new Array(vals.length).fill(null);

        let i = 0;
        while (i < vals.length) {
            const isActive = Number.isFinite(vals[i]) && vals[i] > 0;
            if (!isActive) {
                i += 1;
                continue;
            }
            const start = i;
            let end = i;
            while (end + 1 < vals.length && Number.isFinite(vals[end + 1]) && vals[end + 1] > 0) {
                end += 1;
            }

            let peak = 0;
            for (let j = start; j <= end; j++) {
                peak = Math.max(peak, Number(vals[j]) || 0);
            }

            const span = Math.max(1, end - start);
            for (let j = start; j <= end; j++) {
                const t = (j - start) / span;
                // Full bell envelope (rise + fall), blended with real lux to keep real trend.
                const bell = Math.sin(Math.PI * t);
                const real = Number(vals[j]) || 0;
                const envelope = peak * bell;
                // Blend preserves data trend while keeping curved wave shape.
                out[j] = Math.max(0, (real * 0.7) + (envelope * 0.3));
            }

            i = end + 1;
        }
        return out.map((v) => (Number.isFinite(v) ? Math.max(0, Math.min(GRAPH_MAX_LUX, v)) : null));
    }

    function update(series1, series2, showLine1, showLine2) {
        if (!chartInstance) return;
        const toLux = (series) => (series || []).map((v) => {
            const n = Number(v);
            return Number.isFinite(n) ? Math.max(0, Math.min(GRAPH_MAX_LUX, n)) : null;
        });
        const toVisualBand = (series, bandMin, bandMax) => {
            const positive = (series || []).filter((v) => Number.isFinite(v) && v > 0);
            if (!positive.length) return (series || []).slice();
            const minVal = Math.min(...positive);
            const maxVal = Math.max(...positive);
            const range = maxVal - minVal;
            const mapped = (series || []).map((v) => {
                if (!Number.isFinite(v)) return null;
                if (v <= 0) return 0;
                if (range <= 0) return (bandMin + bandMax) / 2;
                const eased = 1 - Math.pow(1 - ((v - minVal) / range), 1.35);
                return Math.max(0, Math.min(GRAPH_MAX_LUX, bandMin + eased * (bandMax - bandMin)));
            });
            // Force the first visible point to touch the x-axis.
            const firstVisible = mapped.findIndex((v) => Number.isFinite(v));
            if (firstVisible >= 0) {
                // Draw baseline from x=0 up to first visible sample.
                for (let i = 0; i < firstVisible; i++) mapped[i] = 0;
                mapped[firstVisible] = 0;
            }
            return mapped;
        };
        const s1RawLux = toLux(series1);
        const s2RawLux = toLux(series2);
        const s1Lux = smoothLuxSeries(s1RawLux);
        const s2Lux = smoothLuxSeries(s2RawLux);
        const s1Shaped = shapeWaveFromLux(s1Lux);
        const s2Shaped = shapeWaveFromLux(s2Lux);
        const s1Display = toVisualBand(s1Shaped, 1000, 9000);
        const s2Display = toVisualBand(s2Shaped, 9200, 16800);
        chartInstance.data.labels = makeDayLabels();
        chartInstance.data.datasets[0].rawLuxSeries = showLine1 ? s1Shaped : new Array(POINTS_PER_DAY).fill(null);
        chartInstance.data.datasets[1].rawLuxSeries = showLine2 ? s2Shaped : new Array(POINTS_PER_DAY).fill(null);
        chartInstance.data.datasets[0].data = showLine1 ? s1Display : new Array(POINTS_PER_DAY).fill(null);
        chartInstance.data.datasets[1].data = showLine2 ? s2Display : new Array(POINTS_PER_DAY).fill(null);
        chartInstance.update();
    }

    global.TodayUsageChartHelper = {
        init,
        update
    };
})(window);
