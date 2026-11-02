import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Marker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import { divIcon } from 'leaflet'
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
  can_edit: boolean
  can_manage_access: boolean
}
type SoilFeature = {
  geometry: { coordinates: [number, number] }
  properties: SoilProperties
}
type SoilFeatureCollection = { features: SoilFeature[] }
type SampleGroup = { key: string; latitude: number; longitude: number; samples: SoilFeature[] }
type MeasurementRange = { sample_count: number; minimum: number | string | null; maximum: number | string | null }
type SoilRangeReport = {
  sample_count: number
  first_sampled_at: string | null
  last_sampled_at: string | null
  measurements: Record<string, MeasurementRange>
}
type LocationRecommendation = {
  status: 'no_local_samples' | 'context_required' | 'calibration_not_configured'
  soil_summary: SoilRangeReport
  missing_context: string[]
  guidance: string[]
  ai_assisted: boolean
  ai_explanation: string | null
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

function SampleEditPage({ sampleId }: { sampleId: string }) {
  const [sample, setSample] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetch(`/api/v1/soil-samples/${encodeURIComponent(sampleId)}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(response.status === 403 ? 'You do not have access to edit this sample.' : 'Sample could not be loaded.')
        setSample(await response.json() as Record<string, unknown>)
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Sample could not be loaded.'))
  }, [sampleId])

  const saveChanges = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    const form = new FormData(event.currentTarget)
    const payload: Record<string, string | number> = {}
    form.forEach((value, key) => {
      if (typeof value !== 'string' || !value) return
      if (key === 'sampled_at') payload[key] = new Date(value).toISOString()
      else if (key !== 'sample_id' && key !== 'field_name') payload[key] = Number(value)
      else payload[key] = value
    })
    try {
      const response = await fetch(`/api/v1/soil-samples/${encodeURIComponent(sampleId)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      const result = await response.json() as { detail?: string }
      if (!response.ok) throw new Error(result.detail ?? 'Sample could not be updated.')
      window.location.href = '/'
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Sample could not be updated.')
      setSaving(false)
    }
  }

  const value = (key: string) => sample?.[key] == null ? '' : String(sample[key])
  const localDate = sample?.sampled_at ? new Date(String(sample.sampled_at)).toISOString().slice(0, 16) : ''
  if (error && !sample) return <main className="app-shell form-page"><header className="topbar"><a className="brand" href="/"><span className="brand-mark">SP</span><span>Soil Pipeline</span></a></header><p className="report-error">{error}</p></main>
  if (!sample) return <main className="app-shell form-page"><header className="topbar"><a className="brand" href="/"><span className="brand-mark">SP</span><span>Soil Pipeline</span></a></header><p className="form-note">Loading sample…</p></main>
  return <main className="app-shell form-page"><header className="topbar"><a className="brand" href="/"><span className="brand-mark">SP</span><span>Soil Pipeline</span></a><nav><a href="/">Dashboard</a><a className="signin" href="/auth/logout">Sign out</a></nav></header><section className="form-intro"><p className="eyebrow">SAMPLE MANAGEMENT / EDIT</p><h1>Update a soil sample</h1><p className="lede">Changes are limited to you and other users granted editor access.</p></section><form className="sample-form" onSubmit={saveChanges}><fieldset><legend>Sample details</legend><div className="form-grid"><label>Sample ID<input name="sample_id" value={value('sample_id')} readOnly /></label><label>Field name<input name="field_name" defaultValue={value('field_name')} /></label><label>Sample date *<input name="sampled_at" type="datetime-local" defaultValue={localDate} required /></label><label>Depth (inches)<input name="sampling_depth_inches" type="number" step="0.01" defaultValue={value('sampling_depth_inches')} /></label></div></fieldset><fieldset><legend>Location</legend><div className="form-grid"><label>Latitude *<input name="latitude" type="number" step="any" defaultValue={value('latitude')} required /></label><label>Longitude *<input name="longitude" type="number" step="any" defaultValue={value('longitude')} required /></label></div></fieldset><fieldset><legend>Measurements</legend><div className="form-grid three"><label>pH<input name="soil_ph" type="number" min="0" max="14" step="0.01" defaultValue={value('soil_ph')} /></label><label>Organic matter (%)<input name="organic_matter_pct" type="number" min="0" max="100" step="0.01" defaultValue={value('organic_matter_pct')} /></label><label>Nitrogen (ppm)<input name="nitrate_nitrogen_ppm" type="number" min="0" step="0.01" defaultValue={value('nitrate_nitrogen_ppm')} /></label><label>Phosphorus (ppm)<input name="phosphorus_ppm" type="number" min="0" step="0.01" defaultValue={value('phosphorus_ppm')} /></label><label>Potassium (ppm)<input name="potassium_ppm" type="number" min="0" step="0.01" defaultValue={value('potassium_ppm')} /></label><label>Sand (%)<input name="sand_pct" type="number" min="0" max="100" step="0.01" defaultValue={value('sand_pct')} /></label><label>Silt (%)<input name="silt_pct" type="number" min="0" max="100" step="0.01" defaultValue={value('silt_pct')} /></label><label>Clay (%)<input name="clay_pct" type="number" min="0" max="100" step="0.01" defaultValue={value('clay_pct')} /></label></div></fieldset>{error && <p className="report-error">{error}</p>}<div className="form-actions"><a className="secondary-button" href="/">Cancel</a><button className="primary-button report-button" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save changes'}</button></div></form></main>
}

function SampleAccessPage({ sampleId }: { sampleId: string }) {
  const [access, setAccess] = useState<{ email: string; role: string }[]>([])
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('viewer')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const loadAccess = useCallback(() => fetch(`/api/v1/soil-samples/${encodeURIComponent(sampleId)}/access`).then(async (response) => { if (!response.ok) throw new Error('Only the sample owner can manage access.') ; setAccess(await response.json() as { email: string; role: string }[]) }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Access list could not be loaded.')), [sampleId])
  useEffect(() => { void loadAccess() }, [loadAccess])
  const grant = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); setSaving(true); setError(null); try { const response = await fetch(`/api/v1/soil-samples/${encodeURIComponent(sampleId)}/access`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, role }) }); const result = await response.json() as { detail?: string }; if (!response.ok) throw new Error(result.detail ?? 'Access could not be granted.'); setEmail(''); await loadAccess() } catch (reason: unknown) { setError(reason instanceof Error ? reason.message : 'Access could not be granted.') } finally { setSaving(false) } }
  const revoke = async (userEmail: string) => { await fetch(`/api/v1/soil-samples/${encodeURIComponent(sampleId)}/access/${encodeURIComponent(userEmail)}`, { method: 'DELETE' }); await loadAccess() }
  return <main className="app-shell form-page"><header className="topbar"><a className="brand" href="/"><span className="brand-mark">SP</span><span>Soil Pipeline</span></a><nav><a href="/">Dashboard</a><a className="signin" href="/auth/logout">Sign out</a></nav></header><section className="form-intro"><p className="eyebrow">SAMPLE MANAGEMENT / SHARING</p><h1>Manage access</h1><p className="lede">Invite another signed-in user to view or edit this sample.</p></section><section className="access-card"><form className="report-form" onSubmit={grant}><label>Email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="farmer@example.com" required /></label><label>Permission<select value={role} onChange={(event) => setRole(event.target.value)}><option value="viewer">Can view</option><option value="editor">Can edit</option></select></label><button className="primary-button report-button" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Grant access'}</button></form>{error && <p className="report-error">{error}</p>}<div className="access-list"><h3>Current access</h3>{access.length === 0 ? <p className="form-note">No additional users have access.</p> : access.map((entry) => <div className="access-row" key={entry.email}><span>{entry.email}</span><span>{entry.role}</span><button type="button" onClick={() => void revoke(entry.email)}>Revoke</button></div>)}</div></section></main>
}

function ArchiveSamplePage({ sampleId }: { sampleId: string }) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const archive = async () => {
    setSaving(true)
    setError(null)
    try {
      const response = await fetch(`/api/v1/soil-samples/${encodeURIComponent(sampleId)}/archive`, { method: 'POST' })
      const result = await response.json() as { detail?: string }
      if (!response.ok) throw new Error(result.detail ?? 'Sample could not be archived.')
      window.location.href = '/'
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Sample could not be archived.')
      setSaving(false)
    }
  }
  return <main className="app-shell form-page"><header className="topbar"><a className="brand" href="/"><span className="brand-mark">SP</span><span>Soil Pipeline</span></a><nav><a href="/">Dashboard</a><a className="signin" href="/auth/logout">Sign out</a></nav></header><section className="form-intro"><p className="eyebrow">SAMPLE MANAGEMENT / ARCHIVE</p><h1>Archive this sample?</h1><p className="lede">The sample will be removed from the map and reports, but its history and access records will be preserved. You can restore it later through the API.</p></section><div className="form-actions archive-actions"><a className="secondary-button" href="/">Keep sample</a><button className="primary-button archive-button" type="button" onClick={() => void archive()} disabled={saving}>{saving ? 'Archiving…' : 'Archive sample'}</button></div>{error && <p className="report-error">{error}</p>}</main>
}

type ManagedSample = {
  id: number
  sample_id: string
  field_name: string | null
  sampled_at: string
  latitude: number | null
  longitude: number | null
  soil_ph: number | string | null
  archived_at: string | null
}

function MySamplesPage() {
  const [samples, setSamples] = useState<ManagedSample[]>([])
  const [includeArchived, setIncludeArchived] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busySampleId, setBusySampleId] = useState<string | null>(null)

  const loadSamples = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/v1/soil-samples/mine?include_archived=${includeArchived}`, { cache: 'no-store' })
      if (response.status === 401) throw new Error('Sign in to view your samples.')
      if (!response.ok) throw new Error(`The sample service returned ${response.status}.`)
      setSamples(await response.json() as ManagedSample[])
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Unable to load your samples.')
    } finally {
      setLoading(false)
    }
  }, [includeArchived])

  useEffect(() => {
    fetch(`/api/v1/soil-samples/mine?include_archived=${includeArchived}`, { cache: 'no-store' })
      .then(async (response) => {
        if (response.status === 401) throw new Error('Sign in to view your samples.')
        if (!response.ok) throw new Error(`The sample service returned ${response.status}.`)
        return response.json() as Promise<ManagedSample[]>
      })
      .then((data) => { setSamples(data); setError(null) })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unable to load your samples.'))
      .finally(() => setLoading(false))
  }, [includeArchived])

  const changeArchiveState = async (sample: ManagedSample) => {
    const action = sample.archived_at ? 'restore' : 'archive'
    if (!sample.archived_at && !window.confirm(`Archive ${sample.sample_id}? It will be removed from the map and reports.`)) return
    setBusySampleId(sample.sample_id)
    setError(null)
    try {
      const response = await fetch(`/api/v1/soil-samples/${encodeURIComponent(sample.sample_id)}/${action}`, { method: 'POST' })
      const result = await response.json() as { detail?: string }
      if (!response.ok) throw new Error(result.detail ?? `Sample could not be ${action}d.`)
      await loadSamples()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : `Sample could not be ${action}d.`)
    } finally {
      setBusySampleId(null)
    }
  }

  return <main className="app-shell form-page"><header className="topbar"><a className="brand" href="/"><span className="brand-mark">SP</span><span>Soil Pipeline</span></a><nav><a href="/">Dashboard</a><a className="signin" href="/auth/logout">Sign out</a></nav></header><section className="form-intro"><p className="eyebrow">SAMPLE MANAGEMENT / OWNED DATA</p><h1>My samples</h1><p className="lede">Review the field samples you entered, update them, manage access, or archive records that are no longer active.</p></section><section className="sample-library"><div className="library-toolbar"><label className="archive-toggle"><input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} /> Include archived samples</label><a className="primary-button manual-button" href="/samples/new">Add sample</a></div>{error && <p className="report-error">{error}</p>}{loading ? <p className="form-note">Loading your samples…</p> : samples.length === 0 ? <div className="empty-library"><h3>{includeArchived ? 'No samples yet' : 'No active samples'}</h3><p>{includeArchived ? 'Samples you enter or upload will appear here.' : 'Archived samples are hidden. Turn on the archived filter to include them.'}</p></div> : <div className="sample-list">{samples.map((sample) => <article className={`sample-row${sample.archived_at ? ' archived-sample' : ''}`} key={sample.id}><div><span className="sample-status">{sample.archived_at ? 'Archived' : 'Active'}</span><h3>{sample.sample_id}</h3><p>{sample.field_name ?? 'Unnamed field'} · {new Date(sample.sampled_at).toLocaleDateString()}</p><p className="sample-coordinates">{sample.latitude === null || sample.longitude === null ? 'No map coordinates' : `${sample.latitude}, ${sample.longitude}`} · pH {sample.soil_ph ?? 'Not recorded'}</p></div><div className="sample-row-actions">{!sample.archived_at && <><a className="secondary-button" href={`/samples/${encodeURIComponent(sample.sample_id)}/edit`}>Edit</a><a className="secondary-button" href={`/samples/${encodeURIComponent(sample.sample_id)}/access`}>Manage access</a></>}<button className={sample.archived_at ? 'secondary-button' : 'archive-button'} type="button" onClick={() => void changeArchiveState(sample)} disabled={busySampleId === sample.sample_id}>{busySampleId === sample.sample_id ? 'Saving…' : sample.archived_at ? 'Restore' : 'Archive'}</button></div></article>)}</div>}</section></main>
}

function App() {
  const [samples, setSamples] = useState<SoilFeature[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [colorMetric, setColorMetric] = useState<MetricKey>('soil_ph')
  const [recommendation, setRecommendation] = useState<LocationRecommendation | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportError, setReportError] = useState<string | null>(null)
  const [reportLatitude, setReportLatitude] = useState('42.03')
  const [reportLongitude, setReportLongitude] = useState('-93.62')
  const [reportRadius, setReportRadius] = useState('50')
  const [reportCrop, setReportCrop] = useState('')
  const [reportRegion, setReportRegion] = useState('')
  const [reportYieldGoal, setReportYieldGoal] = useState('')
  const [reportYieldUnit, setReportYieldUnit] = useState('')
  const [reportSoilLab, setReportSoilLab] = useState('')
  const [reportSoilMethod, setReportSoilMethod] = useState('')
  const [includeAiExplanation, setIncludeAiExplanation] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadResult, setUploadResult] = useState<BatchResult | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const loadSamples = useCallback(async () => {
    setLoading(true)
    setError(null)
    const query = new URLSearchParams({ west: String(bounds.west), south: String(bounds.south), east: String(bounds.east), north: String(bounds.north), limit: '1000' })
    try {
      const response = await fetch(`/api/v1/maps/soil-samples?${query}`, { cache: 'no-store' })
      if (response.status === 401) throw new Error('Sign in to view soil samples.')
      if (!response.ok) throw new Error(`The sample service returned ${response.status}.`)
      setSamples((await response.json() as SoilFeatureCollection).features)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Unable to load samples.')
      throw reason
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const query = new URLSearchParams({ west: String(bounds.west), south: String(bounds.south), east: String(bounds.east), north: String(bounds.north), limit: '1000' })
    fetch(`/api/v1/maps/soil-samples?${query}`, { cache: 'no-store' })
      .then(async (response) => {
        if (response.status === 401) throw new Error('Sign in to view soil samples.')
        if (!response.ok) throw new Error(`The sample service returned ${response.status}.`)
        return response.json() as Promise<SoilFeatureCollection>
      })
      .then((data) => { setSamples(data.features); setError(null) })
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

  const groupedSamples = useMemo<SampleGroup[]>(() => {
    const groups = new Map<string, SampleGroup>()
    samples.forEach((sample) => {
      const [longitude, latitude] = sample.geometry.coordinates
      const key = `${latitude},${longitude}`
      const group = groups.get(key)
      if (group) group.samples.push(sample)
      else groups.set(key, { key, latitude, longitude, samples: [sample] })
    })
    return Array.from(groups.values())
  }, [samples])

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
      const payload: Record<string, string | number | boolean> = {
        latitude: Number(reportLatitude),
        longitude: Number(reportLongitude),
        radius_km: Number(reportRadius),
        include_ai_explanation: includeAiExplanation,
      }
      if (reportCrop) payload.crop = reportCrop
      if (reportRegion) payload.state_province = reportRegion
      if (reportYieldGoal) payload.yield_goal = Number(reportYieldGoal)
      if (reportYieldUnit) payload.yield_goal_unit = reportYieldUnit
      if (reportSoilLab) payload.soil_test_lab = reportSoilLab
      if (reportSoilMethod) payload.soil_test_method = reportSoilMethod
      const response = await fetch('/api/v1/recommendations/location', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      if (response.status === 401) throw new Error('Sign in to run a soil report.')
      const result = await response.json() as LocationRecommendation | { detail?: string }
      if (!response.ok) throw new Error('detail' in result && result.detail ? result.detail : `The recommendation service returned ${response.status}.`)
      setRecommendation(result as LocationRecommendation)
    } catch (reason: unknown) {
      setReportError(reason instanceof Error ? reason.message : 'Unable to run the report.')
    } finally {
      setReportLoading(false)
    }
  }

  const report = recommendation?.soil_summary
  const reportMeasurement = (name: string) => report?.measurements[name]
  const formatMeasurement = (value: number | string | null) => {
    const parsed = numericValue(value)
    return parsed === null ? '—' : parsed.toFixed(2)
  }

  if (window.location.pathname === '/samples') return <MySamplesPage />
  if (window.location.pathname === '/samples/new') return <AddSamplePage />
  const editMatch = window.location.pathname.match(/^\/samples\/([^/]+)\/edit$/)
  if (editMatch) return <SampleEditPage sampleId={decodeURIComponent(editMatch[1])} />
  const accessMatch = window.location.pathname.match(/^\/samples\/([^/]+)\/access$/)
  if (accessMatch) return <SampleAccessPage sampleId={decodeURIComponent(accessMatch[1])} />
  const archiveMatch = window.location.pathname.match(/^\/samples\/([^/]+)\/archive$/)
  if (archiveMatch) return <ArchiveSamplePage sampleId={decodeURIComponent(archiveMatch[1])} />

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
          <a href="/samples">My samples</a><a href="/samples/new">Add sample</a><a href="/docs" target="_blank" rel="noreferrer">API docs</a>
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
          <details className="recommendation-context">
            <summary>Add recommendation context</summary>
            <div className="recommendation-fields">
              <label>Crop<input value={reportCrop} onChange={(event) => setReportCrop(event.target.value)} placeholder="Corn" /></label>
              <label>State / region<input value={reportRegion} onChange={(event) => setReportRegion(event.target.value)} placeholder="Iowa" /></label>
              <label>Yield goal<input type="number" min="0" step="any" value={reportYieldGoal} onChange={(event) => setReportYieldGoal(event.target.value)} placeholder="200" /></label>
              <label>Yield unit<input value={reportYieldUnit} onChange={(event) => setReportYieldUnit(event.target.value)} placeholder="bu/acre" /></label>
              <label>Soil test lab<input value={reportSoilLab} onChange={(event) => setReportSoilLab(event.target.value)} placeholder="Example Lab" /></label>
              <label>Test method<input value={reportSoilMethod} onChange={(event) => setReportSoilMethod(event.target.value)} placeholder="Mehlich-3" /></label>
            </div>
          </details>
          <label className="ai-toggle"><input type="checkbox" checked={includeAiExplanation} onChange={(event) => setIncludeAiExplanation(event.target.checked)} /> Generate AI explanation <span>optional</span></label>
          <button className="primary-button report-button" type="submit" disabled={reportLoading}>{reportLoading ? 'Preparing…' : 'Run soil brief'}</button>
        </form>
        {reportError && <p className="report-error">{reportError}</p>}
        {recommendation && <div className="report-result"><div className="report-result-head"><div><span className="result-label">Nearby samples</span><strong>{report?.sample_count}</strong></div><span className="result-date">{report?.first_sampled_at ? `Sample window: ${new Date(report.first_sampled_at).toLocaleDateString()} – ${new Date(report.last_sampled_at ?? report.first_sampled_at).toLocaleDateString()}` : 'No dated samples found'}</span></div><div className="report-measurements">{[['soil_ph', 'pH'], ['organic_matter_pct', 'Organic matter %'], ['sand_pct', 'Sand %'], ['silt_pct', 'Silt %'], ['clay_pct', 'Clay %']].map(([key, label]) => { const measurement = reportMeasurement(key); return <div key={key}><span>{label}</span><strong>{measurement ? `${formatMeasurement(measurement.minimum)}–${formatMeasurement(measurement.maximum)}` : '—'}</strong></div> })}</div><div className="recommendation-guidance"><div><span className="result-label">Brief status</span><strong>{recommendation.status.replaceAll('_', ' ')}</strong></div><ul>{recommendation.guidance.map((item) => <li key={item}>{item}</li>)}</ul>{recommendation.missing_context.length > 0 && <p className="form-note">Missing context: {recommendation.missing_context.join(', ')}.</p>}{recommendation.ai_explanation && <div className="ai-explanation"><span className="result-label">AI explanation</span><p>{recommendation.ai_explanation}</p><small>AI explains the aggregate summary only; it does not provide application rates.</small></div>}</div></div>}
      </section>
      <section className="map-section">
        <div className="section-heading"><div><p className="eyebrow">MAP / SAMPLE LOCATIONS</p><h2>Soil sample coverage</h2></div><div className="section-actions"><button className="secondary-button" type="button" onClick={() => void loadSamples().catch(() => undefined)} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh map'}</button><label className="metric-picker">Color by<select value={colorMetric} onChange={(event) => setColorMetric(event.target.value as MetricKey)}>{Object.entries(metricLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label></div></div>
        <div className="map-frame">
          <MapContainer center={initialCenter} zoom={6} scrollWheelZoom className="soil-map">
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            {groupedSamples.map((group) => {
              const selectedValues = group.samples.map((sample) => numericValue(sample.properties[colorMetric])).filter((value): value is number => value !== null)
              const groupValue = selectedValues.length ? selectedValues.reduce((sum, value) => sum + value, 0) / selectedValues.length : null
              const markerIcon = divIcon({ className: 'soil-marker-wrapper', html: `<span class="soil-marker${group.samples.length > 1 ? ' soil-marker-cluster' : ''}" style="background:${colorForValue(groupValue)}">${group.samples.length > 1 ? group.samples.length : ''}</span>` })
              return <Marker key={group.key} position={[group.latitude, group.longitude]} icon={markerIcon} eventHandlers={{ click: () => { setReportLatitude(String(group.latitude)); setReportLongitude(String(group.longitude)) } }}><Popup><strong>{group.samples.length > 1 ? `${group.samples.length} samples at this location` : group.samples[0].properties.sample_id}</strong>{group.samples.map((sample) => { const ph = numericValue(sample.properties.soil_ph); const selectedValue = numericValue(sample.properties[colorMetric]); return <div className="sample-popup-entry" key={sample.properties.sample_id}><strong>{sample.properties.sample_id}</strong><br />{sample.properties.field_name ?? 'Unnamed field'}<br />{colorMetric !== 'soil_ph' && <>{metricLabels[colorMetric]}: {selectedValue === null ? 'Not recorded' : selectedValue}<br /></>}pH: {ph === null ? 'Not recorded' : ph}<br />Sampled: {new Date(sample.properties.sampled_at).toLocaleDateString()}<br />{sample.properties.can_edit && <a className="popup-action" href={`/samples/${encodeURIComponent(sample.properties.sample_id)}/edit`}>Edit sample</a>}{sample.properties.can_manage_access && <><br /><a className="popup-action" href={`/samples/${encodeURIComponent(sample.properties.sample_id)}/access`}>Manage access</a><br /><a className="popup-action archive-link" href={`/samples/${encodeURIComponent(sample.properties.sample_id)}/archive`}>Archive sample</a></>}{!sample.properties.can_edit && !sample.properties.can_manage_access && <span className="popup-summary">Reference data · read-only</span>}</div> })}<span className="popup-summary">Color metric average: {groupValue === null ? 'Not recorded' : groupValue.toFixed(2)}</span></Popup></Marker>
            })}
          </MapContainer>
          {error && <div className="map-overlay"><div className="empty-state"><span className="lock-icon">⌁</span><h3>Authentication required</h3><p>{error}</p><a className="primary-button" href="/auth/login">Continue</a></div></div>}
        </div>
      </section>
    </main>
  )
}

export default App
