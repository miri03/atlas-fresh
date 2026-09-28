import { useState } from 'react'
import { api, describeApiError } from '../api'
import type { AssistantResponse, PlanResult } from '../types'
import { Spinner } from './ui'

const QUICK_QUESTIONS = [
  'Which clients are at risk and why?',
  'What are the biggest farm variances?',
  'Why are 60 t going local and what is their estimated value?',
]

function AnswerBlock({ resp, error }: { resp: AssistantResponse | null; error: string | null }) {
  if (error) {
    return (
      <div className="assistant-message error-banner" role="alert">
        <span className="assistant-error-title">The assistant is unavailable</span>
        <p className="error-message">{error}</p>
      </div>
    )
  }
  if (!resp) return null

  return (
    <div className="assistant-message" aria-live="polite">
      <div className="assistant-meta">
        {resp.mode === 'llm' ? (
          <span className="chip chip-llm">Live model answer</span>
        ) : (
          <span className="chip chip-det" title="No LLM dependency: computed deterministically from the server result">
            Deterministic server summary
          </span>
        )}
        {!resp.configured && (
          <span className="assistant-nokey" role="note">
            No model configured — showing the honest, clearly labelled deterministic summary.
          </span>
        )}
        {resp.configured && resp.using_deterministic_fallback && (
          <span className="assistant-nokey" role="note">
            The model path failed or was rejected — fell back to the deterministic summary.
          </span>
        )}
      </div>
      <div className="assistant-answer">{resp.answer}</div>
      {resp.evidence.length > 0 && (
        <div className="assistant-evidence">
          <span className="evidence-label">Cited from the plan:</span>
          {resp.evidence.map((e) => (
            <code key={e} className="evidence-chip">{e}</code>
          ))}
        </div>
      )}
    </div>
  )
}

export function AssistantPanel({ plan }: { plan: PlanResult }) {
  const [question, setQuestion] = useState('')
  const [resp, setResp] = useState<AssistantResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const contextLine = `Grounded in the current plan: ${plan.data_health.farm_count} farms, ${plan.data_health.client_count} clients, station ${plan.kpis.station_capacity_t} t, export ${plan.kpis.export_t} t, local ${plan.kpis.local_t} t.`

  const ask = async (q: string) => {
    const text = (q ?? '').trim()
    if (!text || busy) return
    setBusy(true)
    setError(null)
    setResp(null)
    try {
      const r = await api.assistant(text)
      setResp(r)
    } catch (e) {
      setError(describeApiError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="section section-assistant" aria-labelledby="assistant-h">
      <header className="section-head">
        <div>
          <h2 id="assistant-h">Planning assistant</h2>
          <p className="section-sub">
            Explains the computed plan only. It never changes allocations — it answers with the same
            server figures and cites the exact farm / client / segment IDs involved.
          </p>
          <p className="section-context">{contextLine}</p>
        </div>
      </header>
      <div className="assistant-panel">
        <div className="quick-questions" role="group" aria-label="Example questions">
          {QUICK_QUESTIONS.map((q) => (
            <button key={q} className="btn btn-chip" onClick={() => ask(q)}>
              {q}
            </button>
          ))}
        </div>
        <form
          className="assistant-form"
          onSubmit={(e) => {
            e.preventDefault()
            void ask(question)
          }}
        >
          <label className="visually-hidden" htmlFor="assistant-q">Ask about the plan</label>
          <textarea
            id="assistant-q"
            className="assistant-input"
            rows={2}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about today's plan, e.g. why is C09 only partially served?"
            disabled={busy}
          />
          <button type="submit" className="btn btn-primary" disabled={busy || !question.trim()}>
            Ask
          </button>
        </form>
        {busy && <Spinner label="Consulting the plan…" />}
        <AnswerBlock resp={resp} error={error} />
      </div>
    </section>
  )
}