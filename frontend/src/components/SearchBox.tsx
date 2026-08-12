interface SearchBoxProps {
  query: string;
  onQueryChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
}

export function SearchBox({
  query,
  onQueryChange,
  onSubmit,
  disabled,
}: SearchBoxProps) {
  return (
    <form
      className="search-box"
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <label className="visually-hidden" htmlFor="search-input">
        Búsqueda en el código
      </label>
      <input
        id="search-input"
        type="search"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder="Pregunta en lenguaje natural… p. ej. ¿dónde se valida el JWT?"
        minLength={2}
        disabled={disabled}
      />
      <div className="search-actions">
        <button type="submit" disabled={disabled || query.trim().length < 2}>
          Buscar
        </button>
      </div>
    </form>
  );
}
