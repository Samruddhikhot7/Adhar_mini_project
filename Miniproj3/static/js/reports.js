/* reports.js - Tabular Reports and Exports */

window.reportsTable = (() => {
    let currentData = [];

    let reportChartInstance = null;

    function initTable(data, summary) {
        currentData = data;
        
        // Populate Narrative
        if (summary && summary.narrative) {
            document.getElementById('report-date').textContent = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
            document.getElementById('narrative-exec-summary').textContent = summary.narrative.exec_summary;
            document.getElementById('narrative-data-abstraction').textContent = summary.narrative.data_abstraction;
            document.getElementById('narrative-analytics').textContent = summary.narrative.analytics;
            document.getElementById('narrative-interpretation').textContent = summary.narrative.interpretation;
            document.getElementById('narrative-recommendation').textContent = summary.narrative.recommendation;
            
            drawReportChart(data);
        }

        renderTable(data);
        
        // Setup Search
        document.getElementById('report-search').addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            const filtered = currentData.filter(d => 
                d.Area.toLowerCase().includes(term) ||
                d.Demand_Zone.toLowerCase().includes(term)
            );
            renderTable(filtered);
        });

        // Setup Exports
        document.getElementById('export-excel').addEventListener('click', exportToExcel);
        document.getElementById('export-pdf').addEventListener('click', exportToPDF);
    }

    function drawReportChart(data) {
        const topData = [...data].sort((a,b) => b.Extra_Centres_Required - a.Extra_Centres_Required).slice(0, 10);
        const ctx = document.getElementById('report-bar-chart').getContext('2d');
        
        if (reportChartInstance) reportChartInstance.destroy();
        
        reportChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: topData.map(d => d.Area),
                datasets: [{
                    label: 'Center Gap',
                    data: topData.map(d => d.Extra_Centres_Required),
                    backgroundColor: '#3b82f6',
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#0f172a' } }
                },
                scales: {
                    x: { ticks: { color: '#0f172a' }, grid: { color: '#e2e8f0' } },
                    y: { ticks: { color: '#0f172a' }, grid: { color: '#e2e8f0' } }
                }
            }
        });
    }

    function renderTable(dataToRender) {
        const tbody = document.getElementById('report-table-body');
        tbody.innerHTML = '';
        
        // Show max 100 for performance if huge, but backend caps at 500 so it's fine.
        dataToRender.forEach(d => {
            const tr = document.createElement('tr');
            
            let badgeClass = 'badge-low';
            if(d.Demand_Zone === 'High') badgeClass = 'badge-high';
            if(d.Demand_Zone === 'Medium') badgeClass = 'badge-medium';

            tr.innerHTML = `
                <td><strong>${d.Area}</strong></td>
                <td>${d.Population.toLocaleString()}</td>
                <td>${d['Estimated_Demand_Next_Year']}</td>
                <td>${d['Existing Centers']}</td>
                <td>${d['Required_Centres_Next_Year']}</td>
                <td style="font-weight: 600;">${d.Extra_Centres_Required}</td>
                <td><span class="badge ${badgeClass}">${d.Demand_Zone}</span></td>
            `;
            tbody.appendChild(tr);
        });
        
        document.getElementById('table-pagination-info').textContent = 
            `Showing ${dataToRender.length > 0 ? 1 : 0} to ${dataToRender.length} of ${dataToRender.length} entries`;
    }

    function exportToExcel() {
        if (currentData.length === 0) return;
        
        // Format for export
        const exportData = currentData.map(d => ({
            'Area': d.Area,
            'Population': d.Population,
            'Aadhaar Requests': d['Estimated_Demand_Next_Year'],
            'Existing Centers': d['Existing Centers'],
            'Predicted Needed': d['Required_Centres_Next_Year'],
            'Center Gap': d.Extra_Centres_Required,
            'Demand Level': d.Demand_Zone,
            'Latitude': d.lat,
            'Longitude': d.lng
        }));

        const worksheet = XLSX.utils.json_to_sheet(exportData);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, "Aadhaar Centers");
        
        // Generate buffer and download
        XLSX.writeFile(workbook, "Aadhaar_Center_Report.xlsx");
        
        Swal.fire({
            icon: 'success',
            title: 'Exported',
            text: 'Excel file downloaded directly.',
            timer: 1500,
            showConfirmButton: false,
            background: document.body.classList.contains('light-theme') ? '#fff' : '#1e293b',
            color: document.body.classList.contains('light-theme') ? '#000' : '#fff'
        });
    }

    function exportToPDF() {
        if (currentData.length === 0) return;
        
        // We will print the entire report document encompassing text, chart and table
        const element = document.getElementById('report-document');
        
        const opt = {
            margin:       1,
            filename:     'Aadhaar_Center_Report.pdf',
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2 },
            jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
        };

        Swal.fire({
            title: 'Generating PDF...',
            text: 'Please wait',
            allowOutsideClick: false,
            didOpen: () => Swal.showLoading()
        });

        html2pdf().set(opt).from(element).save().then(() => {
            Swal.close();
            Swal.fire({
                icon: 'success',
                title: 'Exported',
                text: 'PDF file downloaded.',
                timer: 1500,
                showConfirmButton: false,
                background: document.body.classList.contains('light-theme') ? '#fff' : '#1e293b',
                color: document.body.classList.contains('light-theme') ? '#000' : '#fff'
            });
        });
    }

    return {
        init: (data, summary) => initTable(data, summary)
    };
})();
