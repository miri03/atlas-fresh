// API response types — mirror the pydantic schemas on the server.

export interface ValidationIssue {
  location: string
  message: string
}

export interface ApiError {
  error: string
  detail: string | null
  issues: ValidationIssue[]
}

export interface HealthResponse {
  status: string
  assistant_configured: boolean
}