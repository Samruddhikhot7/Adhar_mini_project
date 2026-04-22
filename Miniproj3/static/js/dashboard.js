/* dashboard.js - Chart.js Visualizations */

window.dashboardChart = (() => {
    let barChart, pieChart, scatterChart, comparisonChart;

    const getColors = () => {
        const isLight = document.body.classList.contains('light-theme');
        return {
            text: isLight ? '#64748b' : '#94a3b8',
            grid: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.05)',
            high: '#ef4444',
            medium: '#f59e0b',
            low: '#10b981',
            primary: '#3b82f6',
            purple: '#8b5cf6'
        };
    };

    const commonOptions = (colors) => ({
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: { color: colors.text, font: { family: "'Inter', sans-serif" } }
            }
        },
        scales: {
            x: { ticks: { color: colors.text }, grid: { color: colors.grid } },
            y: { ticks: { color: colors.text }, grid: { color: colors.grid } }
        }
    });

    function initCharts(data) {
        destroyCharts(); // Clean up if re-initializing
        
        const colors = getColors();
        
        // 1. Bar Chart: Top 15 areas by predicted needed
        const topData = [...data].sort((a,b) => b['Required_Centres_Next_Year'] - a['Required_Centres_Next_Year']).slice(0, 15);
        if (topData.length === 0) topData.push(...data); // fallback

        const ctxBar = document.getElementById('barChart').getContext('2d');
        barChart = new Chart(ctxBar, {
            type: 'bar',
            data: {
                labels: topData.map(d => d.Area),
                datasets: [{
                    label: 'Predicted Required Centers',
                    data: topData.map(d => d['Required_Centres_Next_Year']),
                    backgroundColor: colors.primary,
                    borderRadius: 4
                }]
            },
            options: commonOptions(colors)
        });

        // 2. Pie Chart: Demand Zone Distribution
        const demandCounts = { 'High': 0, 'Medium': 0, 'Low': 0 };
        data.forEach(d => {
            if(demandCounts[d.Demand_Zone] !== undefined) demandCounts[d.Demand_Zone]++;
        });

        const ctxPie = document.getElementById('pieChart').getContext('2d');
        pieChart = new Chart(ctxPie, {
            type: 'doughnut',
            data: {
                labels: ['High Demand', 'Medium Demand', 'Low Demand'],
                datasets: [{
                    data: [demandCounts['High'], demandCounts['Medium'], demandCounts['Low']],
                    backgroundColor: [colors.high, colors.medium, colors.low],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: colors.text, font: { family: "'Inter', sans-serif" }, padding: 20 } }
                },
                cutout: '65%'
            }
        });

        // 3. Scatter Chart: Population vs Required
        const scatterPoints = data.slice(0, 200).map(d => ({
            x: d.Population,
            y: d['Required_Centres_Next_Year'],
            area: d.Area
        }));

        const ctxScatter = document.getElementById('scatterChart').getContext('2d');
        scatterChart = new Chart(ctxScatter, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Centers per Population',
                    data: scatterPoints,
                    backgroundColor: colors.purple,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                ...commonOptions(colors),
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.raw.area}: Pop ${ctx.raw.x.toLocaleString()}, Need ${ctx.raw.y}`
                        }
                    },
                    legend: { display: false }
                }
            }
        });

        // 4. Comparison Chart: Existing vs Predicted
        const compData = [...data].sort((a,b) => b['Required_Centres_Next_Year'] - a['Required_Centres_Next_Year']).slice(0, 10);
        
        const ctxComp = document.getElementById('comparisonChart').getContext('2d');
        comparisonChart = new Chart(ctxComp, {
            type: 'bar',
            data: {
                labels: compData.map(d => d.Area),
                datasets: [
                    {
                        label: 'Existing Centers',
                        data: compData.map(d => d['Existing Centers']),
                        backgroundColor: '#64748b',
                        borderRadius: 4
                    },
                    {
                        label: 'Predicted Needed',
                        data: compData.map(d => d['Required_Centres_Next_Year']),
                        backgroundColor: colors.primary,
                        borderRadius: 4
                    }
                ]
            },
            options: commonOptions(colors)
        });
    }

    function destroyCharts() {
        if(barChart) barChart.destroy();
        if(pieChart) pieChart.destroy();
        if(scatterChart) scatterChart.destroy();
        if(comparisonChart) comparisonChart.destroy();
    }

    return {
        init: (data) => initCharts(data),
        updateTheme: (isLight) => {
            if (!window.appState.isModelTrained) return;
            initCharts(window.appState.data); // Quick and dirty re-render for clean colors
        }
    };
})();
