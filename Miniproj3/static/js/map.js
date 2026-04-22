/* map.js - Geographic Heatmap Visualizations */

window.heatmapMap = (() => {
    let leafletMap = null;
    let markersLayer = null;
    let currentData = [];

    const colors = {
        'High': '#ef4444',
        'Medium': '#f59e0b',
        'Low': '#10b981'
    };

    function initMap(data) {
        currentData = data;
        
        if (!leafletMap) {
            // Init map focused on central India
            leafletMap = L.map('leaflet-map').setView([20.5937, 78.9629], 5);
            
            // Add dark theme friendly tiles
            // Use CartoDB Dark Matter
            const tileLayerObj = L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: 'abcd',
                maxZoom: 20
            });
            tileLayerObj.addTo(leafletMap);
            
            markersLayer = L.featureGroup().addTo(leafletMap);
            
            // Link filter dropdown
            document.getElementById('map-filter').addEventListener('change', (e) => {
                renderMarkers(e.target.value);
            });
        }
        
        renderMarkers('all');
        
        // Wait for tab animation to finish then invalidate size
        setTimeout(() => leafletMap.invalidateSize(), 500);
    }
    
    function renderMarkers(filterZone) {
        markersLayer.clearLayers();
        
        currentData.forEach(point => {
            // Ensure bounds are ok
            if (!point.lat || !point.lng) return;
            
            if (filterZone !== 'all' && point.Demand_Zone !== filterZone) return;
            
            const color = colors[point.Demand_Zone] || '#3b82f6';
            
            const marker = L.circleMarker([point.lat, point.lng], {
                radius: point.Demand_Zone === 'High' ? 8 : (point.Demand_Zone === 'Medium' ? 6 : 4),
                fillColor: color,
                color: '#fff',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            });
            
            const popupContent = `
                <div style="font-family:'Inter',sans-serif; padding:5px;">
                    <h3 style="margin:0 0 5px 0; font-size:14px; border-bottom:1px solid #ccc; padding-bottom:5px;">${point.Area}</h3>
                    <p style="margin:2px 0; font-size:12px;"><strong>Population:</strong> ${point.Population.toLocaleString()}</p>
                    <p style="margin:2px 0; font-size:12px;"><strong>Aadhaar Requests:</strong> ${point['Estimated_Demand_Next_Year']}</p>
                    <p style="margin:2px 0; font-size:12px;"><strong>Existing:</strong> ${point['Existing Centers']}</p>
                    <p style="margin:2px 0; font-size:12px;"><strong>Predicted Needed:</strong> ${point['Required_Centres_Next_Year']}</p>
                    <p style="margin:2px 0; font-size:12px;"><strong>Center Gap:</strong> <span style="color:${color}; font-weight:bold;">${point.Extra_Centres_Required}</span></p>
                    <p style="margin:2px 0; font-size:12px;"><strong>Demand:</strong> ${point.Demand_Zone}</p>
                </div>
            `;
            
            marker.bindPopup(popupContent);
            markersLayer.addLayer(marker);
        });
        
        if (Object.keys(markersLayer._layers).length > 0) {
            leafletMap.fitBounds(markersLayer.getBounds(), { padding: [20, 20], maxZoom: 8 });
        }
    }

    return {
        init: (data) => initMap(data),
        resize: () => {
            if (leafletMap) leafletMap.invalidateSize();
        }
    };
})();
