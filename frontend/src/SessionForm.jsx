// The car, setup, tyre and fuel details that go with a lap. Everything is optional.

export const EMPTY_META = {
  track: 'Monza',
  car: '',
  refCar: '',
  setup: {},
  tyre: { compound: '', wear_start: '', wear_end: '', laps_run: '' },
  fuel: { start: '', end: '' },
  notes: '',
}

const SETUP_FIELDS = [
  ['brake_bias', 'Brake bias %'],
  ['front_wing', 'Front wing'],
  ['rear_wing', 'Rear wing'],
  ['arb_front', 'Front anti roll bar'],
  ['arb_rear', 'Rear anti roll bar'],
  ['diff_preload', 'Diff preload'],
  ['pressure_front', 'Tyre pressure front'],
  ['pressure_rear', 'Tyre pressure rear'],
]

function Box({ label, value, onChange, placeholder, list, wide }) {
  return (
    <label className={'mini' + (wide ? ' wide' : '')}>
      <span>{label}</span>
      <input value={value ?? ''} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} list={list} />
    </label>
  )
}

export default function SessionForm({ meta, onChange }) {
  const set = (patch) => onChange({ ...meta, ...patch })
  const sub = (key, k, v) => set({ [key]: { ...meta[key], [k]: v } })
  return (
    <div className="session-form">
      <div className="mini-grid">
        <Box label="Track" value={meta.track} onChange={(v) => set({ track: v })} list="tracks" />
        <Box label="Your car" value={meta.car} onChange={(v) => set({ car: v })} placeholder="e.g. McLaren 720S GT3" />
        <Box label="Reference car" value={meta.refCar} onChange={(v) => set({ refCar: v })} placeholder="same car if blank" />
        <Box label="Tyre compound" value={meta.tyre.compound} onChange={(v) => sub('tyre', 'compound', v)} placeholder="Medium" />
      </div>
      <datalist id="tracks">
        <option value="Monza" />
        <option value="Spa-Francorchamps" />
        <option value="Nurburgring GP" />
        <option value="Silverstone" />
        <option value="Imola" />
      </datalist>

      <div className="mini-title">Setup used (fill what you know, skip the rest)</div>
      <div className="mini-grid">
        {SETUP_FIELDS.map(([k, label]) => (
          <Box key={k} label={label} value={meta.setup[k]} onChange={(v) => set({ setup: { ...meta.setup, [k]: v } })} />
        ))}
      </div>

      <div className="mini-title">Tyres and fuel across this stint</div>
      <div className="mini-grid">
        <Box label="Laps in stint" value={meta.tyre.laps_run} onChange={(v) => sub('tyre', 'laps_run', v)} />
        <Box label="Tyre wear at start %" value={meta.tyre.wear_start} onChange={(v) => sub('tyre', 'wear_start', v)} placeholder="0" />
        <Box label="Tyre wear at end %" value={meta.tyre.wear_end} onChange={(v) => sub('tyre', 'wear_end', v)} />
        <Box label="Fuel at start (L)" value={meta.fuel.start} onChange={(v) => sub('fuel', 'start', v)} />
        <Box label="Fuel at end (L)" value={meta.fuel.end} onChange={(v) => sub('fuel', 'end', v)} />
        <Box label="Notes" value={meta.notes} onChange={(v) => set({ notes: v })} placeholder="car snaps in turn 7" wide />
      </div>
    </div>
  )
}
