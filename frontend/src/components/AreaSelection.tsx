import type { Area } from '../api/types';
export function AreaSelection({
  areas,
  selected,
  onChange,
  minimum = 2,
}: {
  areas: Area[];
  selected: string[];
  onChange: (ids: string[]) => void;
  minimum?: number;
}) {
  return (
    <fieldset className="selection">
      <legend>Select {minimum === 1 ? 'one to three' : 'two or three'} service areas</legend>
      {areas.map((a) => (
        <label key={a.id}>
          <input
            type="checkbox"
            checked={selected.includes(a.id)}
            disabled={!selected.includes(a.id) && selected.length >= 3}
            onChange={(e) =>
              onChange(
                e.target.checked ? [...selected, a.id] : selected.filter((id) => id !== a.id),
              )
            }
          />
          {a.name}
        </label>
      ))}
    </fieldset>
  );
}
