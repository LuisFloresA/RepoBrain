interface SearchBoxProps {
  query: string;
  onQueryChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  loading?: boolean;
}

export function SearchBox({
  query,
  onQueryChange,
  onSubmit,
  disabled,
  loading,
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
        disabled={disabled || loading}
      />
      <div className="search-actions">
        <button type="submit" disabled={disabled || loading || query.trim().length < 2}>
          {loading ? "Buscando…" : "Buscar"}
        </button>
      </div>
    </form>
  );
}
