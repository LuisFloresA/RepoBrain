import Editor, { type OnMount } from "@monaco-editor/react";
import { useEffect, useRef } from "react";
import type { CodeFile } from "../api/types";
import { maskSecrets } from "../lib/mask";
import { monaco } from "../lib/monaco";

interface CodeViewerProps {
  file: CodeFile;
  highlightLine?: number;
}

function applyHighlight(
  editor: monaco.editor.IStandaloneCodeEditor,
  line?: number,
) {
  const decorations = line
    ? [
        {
          range: new monaco.Range(line, 1, line, 1),
          options: {
            isWholeLine: true,
            className: "rb-highlight",
            linesDecorationsClassName: "rb-line-gutter",
          },
        },
      ]
    : [];
  editor.deltaDecorations([], decorations);
  if (line) {
    editor.revealLineInCenter(line);
  }
}

export function CodeViewer({ file, highlightLine }: CodeViewerProps) {
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);

  const handleMount: OnMount = (editor) => {
    editorRef.current = editor;
    applyHighlight(editor, highlightLine);
  };

  useEffect(() => {
    const editor = editorRef.current;
    if (editor) {
      applyHighlight(editor, highlightLine);
    }
  }, [file, highlightLine]);

  return (
    <div className="code-viewer" data-testid="code-viewer">
      <div className="code-viewer-header">
        <span>{file.path}</span>
        {highlightLine ? (
          <span className="code-viewer-line">línea {highlightLine}</span>
        ) : null}
      </div>
      <Editor
        height="58vh"
        language={file.language ?? undefined}
        value={maskSecrets(file.content)}
        theme="vs-dark"
        onMount={handleMount}
        options={{
          readOnly: true,
          minimap: { enabled: false },
          fontSize: 13,
          scrollBeyondLastLine: false,
          lineNumbers: "on",
          automaticLayout: true,
          renderWhitespace: "none",
        }}
      />
    </div>
  );
}
