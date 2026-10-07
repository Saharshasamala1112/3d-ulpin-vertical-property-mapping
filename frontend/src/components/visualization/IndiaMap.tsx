import { useCallback, useEffect, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { ParcelOption, BuildingOption } from '../../types/geometry';

L.Icon.Default.imagePath = 'https://unpkg.com/leaflet@1.9.4/dist/images';

/**
 * India-centered base map component for parcel/building selection.
 * Renders parcel markers and allows selection for 3D visualization.
 */
export function IndiaMap({
  parcels,
  onParcelSelect,
  onBuildingSelect,
}: {
  parcels: ParcelOption[];
  onParcelSelect: (parcel: ParcelOption | null) => void;
  onBuildingSelect: (building: BuildingOption | null) => void;
}) {
  const [clickedParcel, setClickedParcel] = useState<ParcelOption | null>(null);
  const [clickedBuilding, setClickedBuilding] = useState<BuildingOption | null>(null);

  // India map center (New Delhi) and initial zoom
  const indiaCenter = [28.6139, 77.2090]; // New Delhi coordinates

  // Parcel click handler
  const handleParcelClick = useCallback((parcel: ParcelOption) => {
    setClickedParcel(parcel);
    onParcelSelect(parcel);
  }, [onParcelSelect]);

  // Building click handler
  const handleBuildingClick = useCallback((building: BuildingOption) => {
    setClickedBuilding(building);
    onBuildingSelect(building);
  }, [onBuildingSelect]);

  // Render the Leaflet map
  useEffect(() => {
    // Initialize map only once
    const map = L.map('india-map').setView(indiaCenter, 5);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18,
    }).addTo(map);

    // Render parcel markers
    parcels.forEach((parcel) => {
      const [lon, lat] = parcel.geometry?.centroid
        ? [parcel.geometry.centroid.x, parcel.geometry.centroid.y]
        : [77.2090, 28.6139]; // fallback to Delhi

      const marker = L.marker([lat, lon], {
        riseOnHover: true,
        riseOffset: [0, -5],
      })
        .addTo(map)
        .bindPopup(`
          <b>Parcel ULPI:</b> ${parcel.ulpin}<br />
          <b>Identifier:</b> ${parcel.identifier || 'Surface parcel'}
        `);

      // Store reference for click handling - we'll use a simple approach
      marker.on('click', () => handleParcelClick(parcel));
    });

    // Return cleanup function
    return () => {
      map.remove();
    };
  }, [parcels, handleParcelClick, handleBuildingClick]);

  // Render click indicators and selected info
  return (
    <div style={{ height: '100%', width: '100%' }}>
      <div
        id="india-map"
        style={{
          height: '500px',
          width: '100%',
          borderRadius: '8px',
          overflow: 'hidden',
          border: '1px solid #e2e8f0',
        }}
      />
      {/* Selected parcel info */}
      {clickedParcel && (
        <div
          style={{
            position: 'absolute',
            top: '1rem',
            right: '1rem',
            background: 'var(--surface-card)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            padding: '0.75rem',
            zIndex: 1000,
            maxWidth: '300px',
          }}
        >
          <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.8125rem' }}>
            Selected Parcel
          </h4>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>
              <strong>ULPIN:</strong> {clickedParcel.ulpin}
            </span>
            <button
              onClick={() => onParcelSelect(null)}
              style={{
                background: 'var(--destructive)',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                padding: '4px 8px',
                fontSize: '11px',
                cursor: 'pointer',
              }}
            >
              Deselect
            </button>
          </div>
          <p style={{ margin: '0.25rem 0', fontSize: '0.75rem', color: 'var(--muted)' }}>
            {clickedParcel.identifier || 'Surface parcel'}
          </p>
        </div>
      )}

      {/* Selected building info */}
      {clickedBuilding && (
        <div
          style={{
            position: 'absolute',
            bottom: '1rem',
            right: '1rem',
            background: 'var(--surface-card)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            padding: '0.75rem',
            zIndex: 1000,
            maxWidth: '300px',
          }}
        >
          <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.8125rem' }}>
            Selected Building
          </h4>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>
              <strong>Building ID:</strong> {clickedBuilding.identifier}
            </span>
            <button
              onClick={() => onBuildingSelect(null)}
              style={{
                background: 'var(--destructive)',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                padding: '4px 8px',
                fontSize: '11px',
                cursor: 'pointer',
              }}
            >
              Deselect
            </button>
          </div>
          <p style={{ margin: '0.25rem 0', fontSize: '0.75rem', color: 'var(--muted)' }}>
            {clickedBuilding.name || 'Building'}
          </p>
        </div>
      )}
    </div>
  );
}