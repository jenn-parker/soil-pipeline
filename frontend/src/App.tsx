import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import './App.css'

type SoilProperties = {
  sample_id: string
  field_name: string | null
  sampled_at: string
  soil_ph: number | string | null
  organic_matter_pct: number | string | null
  sand_pct: number | string | null
  silt_pct: number | string | null
  clay_pct: number | string | null
}
type SoilFeature = {
  geometry: { coordinates: [number, number] }
  properties: SoilProperties
}
type SoilFeatureCollection = { features: SoilFeature[] }
type MeasurementRange = { sample_count: number; minimum: number | string | null; maximum: number | string | null }
type SoilRangeReport = {
  sample_count: number
  first_sampled_at: string | null
  last_sampled_at: string | null
  measurements: Record<string, MeasurementRange>
}
type BatchResult = {
  id: number
  filename: string
  status: string
  total_rows: number
  accepted_rows: number
  rejected_rows: number
  errors: { row: number; errors: { field: string; message: string }[] }[]
}

const bounds = { west: -97, south: 40, east: -89, north: 44 }
const initialCenter: [number, number] = [42, -93]
type MetricKey = 'soil_ph' | 'organic_matter_pct' | 'sand_pct' | 'silt_pct' | 'clay_pct'
const metricLabels: Record<MetricKey, string> = {
  soil_ph: 'pH',
  organic_matter_pct: 'Organic matter',
  sand_pct: 'Sand',
  silt_pct: 'Silt',
  clay_pct: 'Clay',
}

function numericValue(value: number | string | null) {
  if (value === null) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function AddSamplePage() {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const saveSample = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    const form = new FormData(event.currentTarget)
    const payload: Record<string, string | number> = {}
    form.forEach((value, key) => {
      if (typeof value !== 'string' || !value) return
      if (key === 'sampled_at') {
        payload[key] = new Date(value).toISOString()
      } else if (['latitude', 'longitude', 'sampling_depth_inches', 'soil_ph', 'organic_matter_pct', 'nitrate_nitrogen_ppm', 'phosphorus_ppm', 'potassium_ppm', 'sand_pct', 'silt_pct', 'clay_pct'].includes(key)) {
        payload[key] = Number(value)
      } else {
        payload[key] = value
      }
    })
    try {
      const response = await fetch('/api/v1/soil-samples', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      const result = await response.json() as { detail?: string }
      if (!response.ok) throw new Error(result.detail ?? `Sample could not be saved (${response.status}).`)
      window.location.href = '/'
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Sample could not be saved.')
      setSaving(false)
    }
  }

  return <main className="app-shell form-page">
    <header className="topbar"><a className="brand" href="/"><span className="brand-mark">SP</span><span>Soil Pipeline</span></a><nav><a href="/">Dashboard</a><a className="signin" href="/auth/logout">Sign out</a></nav></header>
    <section className="form-intro"><p className="eyebrow">FIELD ENTRY / SINGLE SAMPLE</p><h1>Add a soil sample</h1><p className="lede">Enter the values from a lab report or field test. Start with the core measurements; advanced results can be added later.</p></section>
    <form className="sample-form" onSubmit={saveSample}>
      <fieldset><legend>Sample details</legend><div className="form-grid"><label>Sample ID *<input name="sample_id" maxLength={50} placeholder="FIELD-1001" required /></label><label>Field name<input name="field_name" maxLength={100} placeholder="North Field" /></label><label>Sample date *<input name="sampled_at" type="datetime-local" required /></label><label>Depth (inches)<input name="sampling_depth_inches" type="number" min="0" step="0.01" placeholder="6" /></label></div></fieldset>
      <fieldset><legend>Location</legend><div className="form-grid"><label>Latitude *<input name="latitude" type="number" min="-90" max="90" step="any" placeholder="42.0300" required /></label><label>Longitude *<input name="longitude" type="number" min="-180" max="180" step="any" placeholder="-93.6200" required /></label></div><p className="form-note">Use decimal degrees. You can copy coordinates from a map or GPS device.</p></fieldset>
      <fieldset><legend>Core measurements</legend><div className="form-grid three"><label>pH<input name="soil_ph" type="number" min="0" max="14" step="0.01" placeholder="6.4" /></label><label>Organic matter (%)<input name="organic_matter_pct" type="number" min="0" max="100" step="0.01" placeholder="3.5" /></label><label>Nitrogen (ppm)<input name="nitrate_nitrogen_ppm" type="number" min="0" step="0.01" placeholder="18" /></label><label>Phosphorus (ppm)<input name="phosphorus_ppm" type="number" min="0" step="0.01" placeholder="24" /></label><label>Potassium (ppm)<input name="potassium_ppm" type="number" min="0" step="0.01" placeholder="140" /></label></div></fieldset>
      <details className="advanced-fields"><summary>Texture and advanced measurements</summary><div className="form-grid three"><label>Sand (%)<input name="sand_pct" type="number" min="0" max="100" step="0.01" /></label><label>Silt (%)<input name="silt_pct" type="number" min="0" max="100" step="0.01" /></label><label>Clay (%)<input name="clay_pct" type="number" min="0" max="100" step="0.01" /></label></div></details>
      {error && <p className="report-error">{error}</p>}<div className="form-actions"><a className="secondary-button" href="/">Cancel</a><button className="primary-button report-button" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save sample'}</button></div>
    </form>
  </main>
}

function App() {
  const [samples, setSamples] = useState<SoilFeature[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [colorMetric, setColorMetric] = useState<MetricKey>('soil_ph')
  const [report, setReport] = useState<SoilRangeReport | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportError, setReportError] = useState<string | null>(null)
  const [reportLatitude, setReportLatitude] = useState('42.03')
  const [reportLongitude, setReportLongitude] = useState('-93.62')
  const [reportRadius, setReportRadius] = useState('50')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadResult, setUploadResult] = useState<BatchResult | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const loadSamples = async () => {
    const query = new URLSearchParams({ west: String(bounds.west), south: String(bounds.south), east: String(bounds.east), north: String(bounds.north), limit: '1000' })
    const response = await fetch(`/api/v1/maps/soil-samples?${query}`)
    if (response.status === 401) throw new Error('Sign in to view soil samples.')
    if (!response.ok) throw new Error(`The sample service returned ${response.status}.`)
    setSamples((await response.json() as SoilFeatureCollection).features)
  }

  useEffect(() => {
    const query = new URLSearchParams({
      west: String(bounds.west),
      south: String(bounds.south),
      east: String(bounds.east),
      north: String(bounds.north),
      limit: '1000',
    })
    fetch(`/api/v1/maps/soil-samples?${query}`)
      .then(async (response) => {
        if (response.status === 401) throw new Error('Sign in to view soil samples.')
        if (!response.ok) throw new Error(`The sample service returned ${response.status}.`)
        return response.json() as Promise<SoilFeatureCollection>
      })
      .then((data) => setSamples(data.features))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unable to load samples.'))
      .finally(() => setLoading(false))
  }, [])

  const averagePh = useMemo(() => {
    const values = samples
      .map((sample) => numericValue(sample.properties.soil_ph))
      .filter((value): value is number => value !== null)
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
  }, [samples])

  const metricRange = useMemo(() => {
    const values = samples
      .map((sample) => numericValue(sample.properties[colorMetric]))
      .filter((value): value is number => value !== null)
    return values.length ? { min: Math.min(...values), max: Math.max(...values) } : null
  }, [colorMetric, samples])

  const colorForValue = (value: number | null) => {
    if (value === null || !metricRange) return '#d9b86c'
    const spread = metricRange.max - metricRange.min
    const normalized = spread === 0 ? 0.5 : (value - metricRange.min) / spread
    const hue = 18 + normalized * 125
    return `hsl(${hue} 52% 43%)`
  }

  const runReport = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setReportLoading(true)
    setReportError(null)
    try {
      const query = new URLSearchParams({ latitude: reportLatitude, longitude: reportLongitude, radius_km: reportRadius })
      const response = await fetch(`/api/v1/reports/soil-ranges?${query}`)
      if (response.status === 401) throw new Error('Sign in to run a soil report.')
      if (!response.ok) throw new Error(`The report service returned ${response.status}.`)
      setReport(await response.json() as SoilRangeReport)
    } catch (reason: unknown) {
      setReportError(reason instanceof Error ? reason.message : 'Unable to run the report.')
    } finally {
      setReportLoading(false)
    }
  }

  const reportMeasurement = (name: string) => report?.measurements[name]
  const formatMeasurement = (value: number | string | null) => {
    const parsed = numericValue(value)
    return parsed === null ? '—' : parsed.toFixed(2)
  }

  if (window.location.pathname === '/samples/new') return <AddSamplePage />

  const uploadBatch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!uploadFile) return
    setUploadLoading(true)
    setUploadError(null)
    setUploadResult(null)
    try {
      const formData = new FormData()
      formData.append('file', uploadFile)
      const response = await fetch('/api/v1/soil-batches', { method: 'POST', body: formData })
      const payload = await response.json() as BatchResult | { detail?: string }
      if (!response.ok) throw new Error('detail' in payload && payload.detail ? payload.detail : `Upload failed with ${response.status}.`)
      setUploadResult(payload as BatchResult)
      setUploadFile(null)
      await loadSamples()
    } catch (reason: unknown) {
      setUploadError(reason instanceof Error ? reason.message : 'Unable to upload the CSV.')
    } finally {
      setUploadLoading(false)
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/"><span className="brand-mark">SP</span><span>Soil Pipeline</span></a>
        <nav>
          <a href="/samples/new">Add sample</a><a href="/docs" target="_blank" rel="noreferrer">API docs</a>
          {loading || error ? <a className="signin" href="/auth/login">Sign in</a> : <a className="signin" href="/auth/logout">Sign out</a>}
        </nav>
      </header>
      <section className="intro">
        <div><p className="eyebrow">FIELD INTELLIGENCE / SOIL DATA</p><h1>See the ground<br /><em>beneath the operation.</em></h1><p className="lede">A secure workspace for locating soil samples, reviewing field context, and building better agronomic decisions from traceable data.</p></div>
        <div className="status-card"><span className="status-dot" /><div><strong>Data service</strong><span>{loading ? 'Loading samples…' : error ? 'Authentication required' : 'Connected'}</span></div></div>
      </section>
      <section className="metrics" aria-label="Map summary"><div><span>Mapped samples</span><strong>{loading ? '—' : samples.length}</strong></div><div><span>Average pH</span><strong>{averagePh === null ? '—' : averagePh.toFixed(2)}</strong></div><div><span>View extent</span><strong>Midwest</strong></div></section>
      <section className="upload-section">
        <div className="section-heading"><div><p className="eyebrow">INGEST / ADD DATA</p><h2>Add soil data</h2><p className="section-subtitle">Choose how you want to add your field results.</p></div><div className="section-actions"><a className="primary-button manual-button" href="/samples/new">Enter one sample manually</a><span className="map-note">Validated before anything is saved</span></div></div>
        <h3 className="workflow-label">Upload a CSV batch</h3>
        <form className="upload-form" onSubmit={uploadBatch}>
          <label className="file-picker">{uploadFile ? uploadFile.name : 'Choose a UTF-8 CSV file'}<input type="file" accept=".csv,text/csv" onChange={(event) => { setUploadFile(event.target.files?.[0] ?? null); setUploadResult(null); setUploadError(null) }} /></label>
          <button className="primary-button report-button" type="submit" disabled={!uploadFile || uploadLoading}>{uploadLoading ? 'Uploading…' : 'Upload batch'}</button>
        </form>
        <p className="upload-help">Required column: <code>sample_id</code>. Location fields should include <code>latitude</code> and <code>longitude</code> for map placement.</p>
        <details className="csv-format">
          <summary>View CSV format and example</summary>
          <div className="csv-format-content">
            <p><strong>Required:</strong> <code>sample_id</code></p>
            <p><strong>Optional:</strong> <code>field_name</code>, <code>sampled_at</code>, <code>latitude</code>, <code>longitude</code>, <code>soil_ph</code>, <code>organic_matter_pct</code>, <code>sand_pct</code>, <code>silt_pct</code>, <code>clay_pct</code>, <code>nitrate_nitrogen_ppm</code>, <code>phosphorus_ppm</code>, <code>potassium_ppm</code>, <code>bulk_density_g_cm3</code></p>
            <pre><code>{'sample_id,field_name,sampled_at,latitude,longitude,soil_ph,organic_matter_pct\nFIELD-1001,North Field,2026-05-15T00:00:00Z,42.03,-93.62,6.4,3.5'}</code></pre>
            <p className="csv-format-note">Values are validated before insertion. Invalid rows reject the batch without saving any samples.</p>
          </div>
        </details>
        {uploadError && <p className="report-error">{uploadError}</p>}
        {uploadResult && <div className="upload-result"><strong>{uploadResult.status === 'completed' ? 'Batch accepted' : 'Batch rejected'}</strong><span>{uploadResult.filename} · {uploadResult.accepted_rows} accepted · {uploadResult.rejected_rows} rejected</span>{uploadResult.errors.length > 0 && <ul>{uploadResult.errors.slice(0, 4).map((item) => <li key={item.row}>Row {item.row}: {item.errors.map((detail) => `${detail.field} ${detail.message}`).join('; ')}</li>)}</ul>}</div>}
      </section>
      <section className="report-section">
        <div className="section-heading"><div><p className="eyebrow">REPORT / LOCAL CONTEXT</p><h2>Explore a location</h2></div><span className="map-note">Summarize nearby soil measurements</span></div>
        <form className="report-form" onSubmit={runReport}>
          <label>Latitude<input type="number" step="any" min="-90" max="90" value={reportLatitude} onChange={(event) => setReportLatitude(event.target.value)} required /></label>
          <label>Longitude<input type="number" step="any" min="-180" max="180" value={reportLongitude} onChange={(event) => setReportLongitude(event.target.value)} required /></label>
          <label>Radius (km)<input type="number" step="any" min="0.1" max="1000" value={reportRadius} onChange={(event) => setReportRadius(event.target.value)} required /></label>
          <button className="primary-button report-button" type="submit" disabled={reportLoading}>{reportLoading ? 'Running…' : 'Run report'}</button>
        </form>
        {reportError && <p className="report-error">{reportError}</p>}
        {report && <div className="report-result"><div className="report-result-head"><div><span className="result-label">Nearby samples</span><strong>{report.sample_count}</strong></div><span className="result-date">{report.first_sampled_at ? `Sample window: ${new Date(report.first_sampled_at).toLocaleDateString()} – ${new Date(report.last_sampled_at ?? report.first_sampled_at).toLocaleDateString()}` : 'No dated samples found'}</span></div><div className="report-measurements">{[['soil_ph', 'pH'], ['organic_matter_pct', 'Organic matter %'], ['sand_pct', 'Sand %'], ['silt_pct', 'Silt %'], ['clay_pct', 'Clay %']].map(([key, label]) => { const measurement = reportMeasurement(key); return <div key={key}><span>{label}</span><strong>{measurement ? `${formatMeasurement(measurement.minimum)}–${formatMeasurement(measurement.maximum)}` : '—'}</strong></div> })}</div></div>}
      </section>
      <section className="map-section">
        <div className="section-heading"><div><p className="eyebrow">MAP / SAMPLE LOCATIONS</p><h2>Soil sample coverage</h2></div><label className="metric-picker">Color by<select value={colorMetric} onChange={(event) => setColorMetric(event.target.value as MetricKey)}>{Object.entries(metricLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label></div>
        <div className="map-frame">
          <MapContainer center={initialCenter} zoom={6} scrollWheelZoom className="soil-map">
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            {samples.map((sample) => { const [longitude, latitude] = sample.geometry.coordinates; const ph = numericValue(sample.properties.soil_ph); const selectedValue = numericValue(sample.properties[colorMetric]); return <CircleMarker key={sample.properties.sample_id} center={[latitude, longitude]} radius={8} eventHandlers={{ click: () => { setReportLatitude(String(latitude)); setReportLongitude(String(longitude)) } }} pathOptions={{ color: '#174a3b', fillColor: colorForValue(selectedValue), fillOpacity: 0.85 }}><Popup><strong>{sample.properties.sample_id}</strong><br />{sample.properties.field_name ?? 'Unnamed field'}<br />{colorMetric !== 'soil_ph' && <>{metricLabels[colorMetric]}: {selectedValue === null ? 'Not recorded' : selectedValue}<br /></>}pH: {ph === null ? 'Not recorded' : ph}<br />Sampled: {new Date(sample.properties.sampled_at).toLocaleDateString()}</Popup></CircleMarker> })}
          </MapContainer>
          {error && <div className="map-overlay"><div className="empty-state"><span className="lock-icon">⌁</span><h3>Authentication required</h3><p>{error}</p><a className="primary-button" href="/auth/login">Continue</a></div></div>}
        </div>
      </section>
    </main>
  )
}

export default App
