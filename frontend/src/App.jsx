import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { BrowserRouter, NavLink, Navigate, Outlet, Route, Routes, useNavigate } from 'react-router-dom'
import { apiGet, apiPatch, apiPost, apiDelete } from './api'
import html2pdf from 'html2pdf.js/dist/html2pdf.bundle.js'

const reportRanges = {
  'TAC 2': {
    pontuacao_primeira_parte: { min: 0, max: 50 },
    pontuacao_segunda_parte: { min: 0, max: 7 },
    pontuacao_terceira_parte: { min: 0, max: 52 },
  },
  'Teste de Trilhas A e B': {
    resultado_parte_a: { min: 0, max: 24 },
    resultado_parte_b: { min: 0, max: 24 },
    resultado_parte_ba: { min: -24, max: 0 },
  },
  'Torre de Londres': {
    pontuacao_total: { min: 0, max: 36 },
    pontuacao_4_movimentos: { min: 0, max: 12 },
    pontuacao_5_movimentos: { min: 0, max: 12 },
  },
}

const reportMinAges = {
  'TAC 2': 5,
  'Teste de Trilhas A e B': 6,
  'Torre de Londres': 11,
}

// Only digits, auto-format to dd/mm/yyyy
function formatDateInput(value) {
  const digits = String(value).replace(/\D/g, '').slice(0, 8)
  if (digits.length <= 2) return digits
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`
}

// Only digits, auto-format to (00) 00000-0000
function formatPhoneInput(value) {
  const digits = String(value).replace(/\D/g, '').slice(0, 11)
  if (digits.length <= 2) return digits
  if (digits.length <= 7) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`
}

// State of the "Nova Avaliação" page lives here, mounted inside
// ProtectedLayout. Because the layout stays mounted while switching
// between tabs, the page keeps its data (patient, reports, fields,
// preview) when the user navigates away and comes back. The provider
// is unmounted on logout, so the data is fully reset only then.
const GenerateReportContext = createContext(null)

function GenerateReportProvider({ children }) {
  const [patients, setPatients] = useState([])
  const [reportTypes, setReportTypes] = useState([])
  const [selectedPatient, setSelectedPatient] = useState('')
  const [selectedReports, setSelectedReports] = useState([])
  const [loadedReports, setLoadedReports] = useState([])
  const [formData, setFormData] = useState({})
  const [resultHtml, setResultHtml] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [invalidFields, setInvalidFields] = useState({})
  const [patientDescription, setPatientDescription] = useState('')
  const [userIaDirectionConclusion, setUserIaDirectionConclusion] = useState('')

  const value = {
    patients, setPatients,
    reportTypes, setReportTypes,
    selectedPatient, setSelectedPatient,
    selectedReports, setSelectedReports,
    loadedReports, setLoadedReports,
    formData, setFormData,
    resultHtml, setResultHtml,
    message, setMessage,
    loading, setLoading,
    generating, setGenerating,
    invalidFields, setInvalidFields,
    patientDescription, setPatientDescription,
    userIaDirectionConclusion, setUserIaDirectionConclusion,
  }

  return <GenerateReportContext.Provider value={value}>{children}</GenerateReportContext.Provider>
}

function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiGet('/api/auth/user')
      .then((data) => {
        setUser(data.user)
      })
      .catch(() => {
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const logout = async () => {
    await apiPost('/api/auth/logout')
    setUser(null)
  }

  if (loading) {
    return <div className="loading-screen">Carregando...</div>
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage user={user} onLogin={setUser} />} />
        <Route path="/" element={<ProtectedLayout user={user} onLogout={logout} />}>
          <Route index element={<Navigate to="/generate-report" replace />} />
          <Route path="generate-report" element={<GenerateReportPage />} />
          <Route path="patients" element={<PatientsPage />} />
          <Route path="register-patient" element={<RegisterPatientPage />} />
          <Route path="account" element={<AccountPage user={user} onProfileUpdated={setUser} />} />
          <Route path="chat-gemini" element={<ChatGeminiPage />} />
        </Route>
        <Route path="*" element={<Navigate to={user ? '/generate-report' : '/login'} replace />} />
      </Routes>
    </BrowserRouter>
  )
}

function LoginPage({ user, onLogin }) {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (user) {
      navigate('/generate-report', { replace: true })
    }
  }, [user, navigate])

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    if (!email || !password) {
      setError('Email e senha são obrigatórios.')
      return
    }
    try {
      await apiPost('/api/auth/login', { email, password })
      const payload = await apiGet('/api/auth/user')
      onLogin(payload.user)
      navigate('/generate-report')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="page-center">
      <div className="card login-card">
        <img className="login-logo" src="/static/assets/logos/Logo_CogniReport_1.png" alt="CogniReports" />
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <label htmlFor="email">E-mail</label>
            <input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </div>
          <div className="form-row">
            <label htmlFor="password">Senha</label>
            <input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </div>
          <button type="submit" className="button">
            Entrar
          </button>
          {error && <p className="message">{error}</p>}
        </form>
      </div>
    </div>
  )
}

function ProtectedLayout({ user, onLogout }) {
  const [collapsed, setCollapsed] = useState(false)

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className="sidebar">
        <div className="brand-row">
          <img
            className={`brand-logo ${collapsed ? 'clickable' : ''}`}
            src="/static/assets/logos/LOGO_TESTE.png"
            alt="CogniReports"
            onClick={() => collapsed && setCollapsed(false)}
          />
          <div className="brand">
            <span className="brand-cogni">Cogni</span>
            <span className="brand-reports">Reports</span>
          </div>
          <button
            type="button"
            className={`sidebar-toggle ${collapsed ? 'collapsed' : ''}`}
            onClick={() => setCollapsed((current) => !current)}
            aria-label="Alternar menu lateral"
          >
            <svg className="sidebar-toggle-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
        </div>
        <div className="sidebar-divider"></div>
        <nav>
          <NavLink to="/generate-report" className={({ isActive }) => (isActive ? 'active' : '')}>
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
              <path d="M14 3v5h5" />
            </svg>
            <span className="nav-text">Nova Avaliação</span>
          </NavLink>
          <NavLink to="/register-patient" className={({ isActive }) => (isActive ? 'active' : '')}>
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <line x1="19" y1="8" x2="19" y2="14" />
              <line x1="22" y1="11" x2="16" y2="11" />
            </svg>
            <span className="nav-text">Novo Paciente</span>
          </NavLink>
          <NavLink to="/patients" className={({ isActive }) => (isActive ? 'active' : '')}>
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
            <span className="nav-text">Pacientes</span>
          </NavLink>
          <NavLink to="/chat-gemini" className={({ isActive }) => (isActive ? 'active' : '')}>
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            <span className="nav-text">Chat Gemini</span>
          </NavLink>
          <NavLink to="/account" className={({ isActive }) => (isActive ? 'active' : '')}>
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
            <span className="nav-text">Perfil</span>
          </NavLink>
        </nav>
        <button type="button" className="sidebar-logout" onClick={onLogout}>
          <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          <span className="nav-text">Sair</span>
        </button>
      </aside>
      <main className="content">
        <GenerateReportProvider>
          <Outlet />
        </GenerateReportProvider>
      </main>
    </div>
  )
}

function GenerateReportPage() {
  const {
    patients, setPatients,
    reportTypes, setReportTypes,
    selectedPatient, setSelectedPatient,
    selectedReports, setSelectedReports,
    loadedReports, setLoadedReports,
    formData, setFormData,
    resultHtml, setResultHtml,
    message, setMessage,
    loading, setLoading,
    generating, setGenerating,
    invalidFields, setInvalidFields,
    patientDescription, setPatientDescription,
    userIaDirectionConclusion, setUserIaDirectionConclusion,
  } = useContext(GenerateReportContext)
  const reportPreviewRef = useRef(null)

  const escapeHtml = (value) =>
    String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')

  const validateField = (reportName, name, value) => {
    const range = reportRanges[reportName] && reportRanges[reportName][name]
    if (!range || value === '' || value === null || value === undefined) {
      return true
    }
    const numeric = Number(value)
    return !(Number.isNaN(numeric) || numeric < range.min || numeric > range.max)
  }

  useEffect(() => {
    apiGet('/api/patients')
      .then(setPatients)
      .catch((err) => setMessage(err.message))
    apiGet('/api/report-types')
      .then(setReportTypes)
      .catch((err) => setMessage(err.message))
  }, [])

  const loadSelectedReports = async () => {
    if (!selectedReports.length) {
      setMessage('Selecione pelo menos um relatório antes de carregar.')
      return
    }

    if (!selectedPatient) {
      setMessage('Selecione um paciente antes de carregar relatórios.')
      return
    }

    // validate patient age against selected reports
    const patient = patients.find((p) => String(p.id) === String(selectedPatient))
    if (!patient) {
      setMessage('Paciente selecionado não encontrado.')
      return
    }
    const patientAge = Number(patient.age)
    const failing = []
    for (const reportName of selectedReports) {
      const min = reportMinAges[reportName]
      if (min && (Number.isNaN(patientAge) || patientAge < min)) {
        failing.push({ reportName, minRequired: min, patientAge: patient.age || 'N/A' })
      }
    }
    if (failing.length) {
      const parts = failing.map((f) => `"${f.reportName}": mínimo ${f.minRequired} anos (paciente: ${f.patientAge})`)
      setMessage(`Idade insuficiente para: ${parts.join('; ')}`)
      return
    }

    setMessage('')
    setLoading(true)
    try {
      const loaded = []
      const nextForm = { ...formData }
      for (const reportName of selectedReports) {
        const fields = await apiGet(`/api/report-fields?report_name=${encodeURIComponent(reportName)}`)
        loaded.push({ reportName, fields })
        nextForm[reportName] = {}
        fields.forEach((field) => {
          nextForm[reportName][field.name] = ''
        })
      }
      setLoadedReports(loaded)
      setFormData(nextForm)
    } catch (err) {
      setMessage(err.message)
    } finally {
      setLoading(false)
    }
  }

  const toggleReportSelection = (reportName) => {
    // prevent toggling locked reports
    const patient = patients.find((p) => String(p.id) === String(selectedPatient))
    const patientAge = patient ? Number(patient.age) : null
    const min = reportMinAges[reportName]
    if (min && (Number.isNaN(patientAge) || patientAge < min)) {
      return
    }
    setSelectedReports((current) =>
      current.includes(reportName) ? current.filter((name) => name !== reportName) : [...current, reportName]
    )
  }

  // remove any selected reports that become invalid when patient changes
  useEffect(() => {
    if (!selectedPatient) return
    const patient = patients.find((p) => String(p.id) === String(selectedPatient))
    const patientAge = patient ? Number(patient.age) : null
    setSelectedReports((current) => current.filter((r) => {
      const min = reportMinAges[r]
      if (!min) return true
      return !(Number.isNaN(patientAge) || patientAge < min)
    }))
  }, [selectedPatient, patients])

  const handleFieldChange = (reportName, name, value) => {
    setFormData((current) => ({
      ...current,
      [reportName]: {
        ...current[reportName],
        [name]: value,
      },
    }))
    const fieldKey = `${reportName}::${name}`
    const valid = validateField(reportName, name, value)
    setInvalidFields((current) => {
      const next = { ...current }
      if (!valid) {
        next[fieldKey] = true
      } else {
        delete next[fieldKey]
      }
      return next
    })
  }

  const validateInputs = () => {
    for (const report of loadedReports) {
      const rules = reportRanges[report.reportName]
      if (!rules) {
        continue
      }
      const values = formData[report.reportName] || {}
      for (const [field, range] of Object.entries(rules)) {
        const value = values[field]
        if (value === '' || value === null || value === undefined) {
          continue
        }
        const numeric = Number(value)
        if (Number.isNaN(numeric) || numeric < range.min || numeric > range.max) {
          setMessage(`O campo ${field} do relatório ${report.reportName} deve estar entre ${range.min} e ${range.max}.`)
          return false
        }
      }
    }
    return true
  }

  const handleGenerate = async () => {
    setMessage('')
    setResultHtml('')
    if (!selectedPatient || !loadedReports.length) {
      setMessage('Selecione paciente e carregue pelo menos um relatório antes de gerar.')
      return
    }
    if (!validateInputs()) {
      return
    }
    setGenerating(true)
    try {
      const patient = patients.find((p) => String(p.id) === String(selectedPatient))

      // 1) Professional patient header (always present)
      const patientHeader = `
        <section class="pdf-patient-header">
          <div class="pdf-header-title">Relatório de Avaliação Neuropsicológica</div>
          <table class="pdf-patient-table">
            <tbody>
              <tr>
                <th>Paciente</th>
                <td>${escapeHtml(patient?.full_name || '-')}</td>
                <th>Idade</th>
                <td>${escapeHtml(patient?.age || '-')} anos</td>
              </tr>
              <tr>
                <th>Data de nascimento</th>
                <td>${escapeHtml(patient?.birth_date || '-')}</td>
                <th>Gênero</th>
                <td>${escapeHtml(patient?.gender || '-')}</td>
              </tr>
            </tbody>
          </table>
        </section>
      `

      // 2) Patient description written by the user (only if provided)
      const descriptionHtml = patientDescription.trim()
        ? `
          <section class="pdf-patient-description">
            <h2>Descrição do paciente</h2>
            <p>${escapeHtml(patientDescription).replace(/\n/g, '<br />')}</p>
          </section>
        `
        : ''

      // 3) Report results
      const reportParts = []
      for (const report of loadedReports) {
        const response = await fetch('/api/reports', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            patient_id: selectedPatient,
            report_name: report.reportName,
            input_data: formData[report.reportName] || {},
          }),
        })
        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(errorText || `Erro ao gerar relatório ${report.reportName}`)
        }
        const html = await response.text()
        reportParts.push(`<section class="report-result"><h2>${report.reportName}</h2>${html}</section>`)
      }

      // 4) Conclusion generated server-side (at the end of the PDF)
      try {
        const conclusionResp = await fetch('/api/conclusion', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            patient_id: selectedPatient,
            report_results: loadedReports.map((report, index) => ({
              report_name: report.reportName,
              results_html: reportParts[index] || '',
            })),
            patient_description: patientDescription,
            user_ia_direction_conclusion: userIaDirectionConclusion,
          }),
        })
        const conclusionBody = await conclusionResp.text()
        reportParts.push(`<section class="report-result conclusion-section"><h2 class="conclusion-title">Síntese dos resultados</h2>${conclusionBody}</section>`)
      } catch (err) {
        // A conclusão é opcional: se falhar, o preview dos relatórios ainda é exibido
      }

      setResultHtml(`<div class="pdf-document">${patientHeader}${descriptionHtml}${reportParts.join('')}</div>`)
    } catch (err) {
      setMessage(err.message)
    } finally {
      setGenerating(false)
    }
  }

  const handleDownloadPdf = async () => {
    if (!selectedPatient || !loadedReports.length) {
      setMessage('Selecione paciente e carregue pelo menos um relatório antes de baixar PDF.')
      return
    }
    if (!validateInputs()) {
      return
    }
    if (!reportPreviewRef.current) {
      setMessage('Não foi possível gerar o PDF. Tente gerar o relatório novamente.')
      return
    }

    setLoading(true)
    try {
      // scale relative to device pixel ratio for sharper output
      const dpr = Math.min(window.devicePixelRatio || 1, 2.5)
      const options = {
        margin: [10, 10, 10, 10],
        filename: 'relatorio.pdf',
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: Math.max(1.5, dpr * 1.5), useCORS: true, logging: false },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
        pagebreak: { mode: ['css', 'legacy'] },
      }
      await html2pdf().set(options).from(reportPreviewRef.current).save()
    } catch (err) {
      setMessage(err?.message || 'Erro ao gerar PDF do relatório')
    } finally {
      setLoading(false)
    }
  }

  // Auto-scroll to the start of the generated report preview
  useEffect(() => {
    if (resultHtml && reportPreviewRef.current) {
      reportPreviewRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [resultHtml])

  return (
    <div className="generate-page">
      <div className="topbar">
        <section className="page-header">
          <img className="page-icon-image" src="/static/assets/icons/nova-avaliacao.png" alt="Nova Avaliação" />
          <div>
            <h1>Nova Avaliação</h1>
          </div>
        </section>
      </div>
      <div className="form-card">
        <div className="form-row">
          <label>Paciente</label>
          <select value={selectedPatient} onChange={(event) => setSelectedPatient(event.target.value)}>
            <option value="">Selecione um paciente</option>
            {patients.map((patient) => (
              <option key={patient.id} value={patient.id}>
                {patient.full_name} {patient.age ? `- ${patient.age} anos` : ''}
              </option>
            ))}
          </select>
        </div>
          <div className="form-row">
            <label>Tipo de relatório</label>
            <div className="report-cards">
              {
                // order: available first, locked last
                (() => {
                  const patient = patients.find((p) => String(p.id) === String(selectedPatient))
                  const patientAge = patient ? Number(patient.age) : null
                  const unlocked = []
                  const locked = []
                  reportTypes.forEach((type) => {
                    const min = reportMinAges[type]
                    const isLocked = min && (selectedPatient && (Number.isNaN(patientAge) || patientAge < min))
                    if (isLocked) locked.push(type); else unlocked.push(type)
                  })
                  return [...unlocked, ...locked].map((type) => {
                    const min = reportMinAges[type]
                    const isLocked = min && (selectedPatient && (Number.isNaN(patientAge) || patientAge < min))
                    return (
                      <button
                        key={type}
                        type="button"
                        className={`report-card ${selectedReports.includes(type) ? 'selected' : ''} ${isLocked ? 'locked' : ''}`}
                        onClick={() => toggleReportSelection(type)}
                        disabled={isLocked}
                        title={isLocked ? `Idade mínima: ${min} anos` : undefined}
                      >
                        <strong>{type}</strong>
                        <span>{selectedReports.includes(type) ? 'Selecionado' : (isLocked ? `Bloqueado (${min}+)` : 'Clique para selecionar')}</span>
                      </button>
                    )
                  })
                })()
              }
            </div>
          </div>
        <div className="form-row" style={{ marginTop: 10 }}>
          <button type="button" className="button" onClick={loadSelectedReports} disabled={!selectedReports.length || loading}>
            Carregar Relatório
          </button>
        </div>
        {loading && <p>Carregando...</p>}
      </div>

      {loadedReports.length > 0 && (
        <div className="form-card" style={{ marginTop: 20 }}>
          <div className="description-block">
            <h2>Descrição do paciente</h2>
            <textarea
              className="description-textarea"
              rows="4"
              value={patientDescription}
              onChange={(event) => setPatientDescription(event.target.value)}
              placeholder="Escreva aqui uma descrição sobre o paciente..."
            />
          </div>
          <div className="section-divider" />
          {loadedReports.map((report) => (
            <div key={report.reportName} className="report-section">
              <h3>{report.reportName}</h3>
              {report.fields.map((field) => {
                const fieldKey = `${report.reportName}::${field.name}`
                const isInvalid = !!invalidFields[fieldKey]
                return (
                <div key={field.name} className={`form-row ${isInvalid ? 'invalid' : ''}`}>
                  <label>{field.label}</label>
                  {field.type === 'textarea' ? (
                    <textarea
                      value={(formData[report.reportName] || {})[field.name] || ''}
                      placeholder={field.placeholder || ''}
                      onChange={(event) => handleFieldChange(report.reportName, field.name, event.target.value)}
                    />
                  ) : (
                    <input
                      value={(formData[report.reportName] || {})[field.name] || ''}
                      placeholder={field.placeholder || ''}
                      onChange={(event) => handleFieldChange(report.reportName, field.name, event.target.value)}
                    />
                  )}
                </div>
                )
              })}
            </div>
          ))}
          <div className="section-divider" />
          <div className="description-block">
            <h2>Direção pra conclusão</h2>
            <textarea
              className="description-textarea"
              rows="4"
              value={userIaDirectionConclusion}
              onChange={(event) => setUserIaDirectionConclusion(event.target.value)}
              placeholder="Escreva aqui a direção para a conclusão do relatório..."
            />
          </div>
          <div className="form-row">
            <button type="button" className="button" onClick={handleGenerate} disabled={generating}>
              Gerar relatório
            </button>
          </div>
        </div>
      )}

      {message && <p className="message">{message}</p>}
      {resultHtml && (
        <div className="card pdf-preview" style={{ marginTop: 20 }} ref={reportPreviewRef}>
          <div className="pdf-inner" dangerouslySetInnerHTML={{ __html: resultHtml }} />
        </div>
      )}
      {resultHtml && (
        <div className="download-block" style={{ marginTop: 16 }}>
          <button type="button" className="button" onClick={handleDownloadPdf} disabled={loading}>
            Baixar
          </button>
        </div>
      )}
      {generating && <div className="generate-blur-layer" />}
      {generating && (
        <div className="generate-overlay">
          <div className="generate-overlay-spinner" />
          <p className="generate-overlay-title">Gerando relatorios</p>
          <p className="generate-overlay-subtitle">Aguarde alguns instantes....</p>
        </div>
      )}
    </div>
  )
}

function PatientsPage() {
  const [patients, setPatients] = useState([])
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState({})
  const [message, setMessage] = useState('')

  useEffect(() => {
    loadPatients()
  }, [])

  const loadPatients = () => {
    apiGet('/api/patients')
      .then(setPatients)
      .catch((err) => setMessage(err.message))
  }

  const startEdit = (patient) => {
    setEditingId(patient.id)
    setEditForm({
      full_name: patient.full_name,
      birth_date: patient.birth_date || '',
      gender: patient.gender || '',
      phone: patient.phone || '',
      email: patient.email || '',
    })
    setMessage('')
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditForm({})
  }

  const handleChange = (field, value) => {
    setEditForm((current) => ({ ...current, [field]: value }))
  }

  const updatePatient = async (event) => {
    event.preventDefault()
    setMessage('')
    try {
      await apiPatch(`/api/patients/${editingId}`, editForm)
      setMessage('Paciente atualizado com sucesso.')
      setEditingId(null)
      loadPatients()
    } catch (err) {
      setMessage(err.message)
    }
  }

  return (
    <div>
      <div className="topbar">
        <section className="page-header">
          <img className="page-icon-image" src="/static/assets/icons/dados-pacientes.png" alt="Dados dos Pacientes" />
          <div>
            <h1>Pacientes</h1>
          </div>
        </section>
      </div>
      <div className="table-card">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Idade</th>
                <th>Gênero</th>
                <th>Email</th>
                <th>Contato</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {patients.map((patient) => (
                <tr key={patient.id}>
                  <td>{patient.full_name}</td>
                  <td>{patient.age || '-'}</td>
                  <td>{patient.gender || '-'}</td>
                  <td>{patient.email || '-'}</td>
                  <td>{patient.phone || '-'}</td>
                  <td>
                    <button type="button" className="button-secondary" onClick={() => startEdit(patient)}>
                      Editar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {editingId && (
        <div className="form-card" style={{ marginTop: 20 }}>
          <h2>Editar paciente</h2>
          <form onSubmit={updatePatient}>
            <div className="form-row">
              <label>Nome completo</label>
              <input value={editForm.full_name || ''} onChange={(event) => handleChange('full_name', event.target.value)} required />
            </div>
            <div className="grid-two">
              <div className="form-row">
                <label>Data de nascimento</label>
                <input value={editForm.birth_date || ''} onChange={(event) => handleChange('birth_date', formatDateInput(event.target.value))} placeholder="dd/mm/aaaa" />
              </div>
              <div className="form-row">
                <label>Gênero</label>
                <select value={editForm.gender || ''} onChange={(event) => handleChange('gender', event.target.value)}>
                  <option value="">Selecione</option>
                  <option value="Feminino">Feminino</option>
                  <option value="Masculino">Masculino</option>
                  <option value="Outro">Outro</option>
                </select>
              </div>
            </div>
            <div className="grid-two">
              <div className="form-row">
                <label>Email</label>
                <input value={editForm.email || ''} onChange={(event) => handleChange('email', event.target.value)} />
              </div>
              <div className="form-row">
                <label>Telefone</label>
                <input value={editForm.phone || ''} onChange={(event) => handleChange('phone', formatPhoneInput(event.target.value))} placeholder="(00) 00000-0000" />
              </div>
            </div>
            <div className="form-row">
              <button type="submit" className="button">
                Salvar
              </button>
              <button type="button" className="button-secondary" onClick={cancelEdit}>
                Cancelar
              </button>
            </div>
          </form>
        </div>
      )}
      {message && <p className={message.includes('sucesso') ? 'success' : 'message'}>{message}</p>}
    </div>
  )
}

function RegisterPatientPage() {
  const [patients, setPatients] = useState([])
  const [form, setForm] = useState({ full_name: '', birth_date: '', gender: '', phone: '', email: '' })
  const [message, setMessage] = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)

  useEffect(() => {
    loadPatients()
  }, [])

  const loadPatients = () => {
    apiGet('/api/patients')
      .then(setPatients)
      .catch((err) => setMessage(err.message))
  }

  const confirmDelete = (patient) => {
    setMessage('')
    setDeleteTarget(patient)
  }

  const cancelDelete = () => {
    setDeleteTarget(null)
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setMessage('')
    try {
      await apiDelete(`/api/patients/${deleteTarget.id}`)
      setMessage('Paciente excluído com sucesso.')
      setDeleteTarget(null)
      loadPatients()
    } catch (err) {
      setMessage(err.message)
      setDeleteTarget(null)
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setMessage('')
    if (!form.full_name.trim()) {
      setMessage('Nome completo é obrigatório.')
      return
    }
    try {
      await apiPost('/api/patients', form)
      setMessage('Paciente cadastrado com sucesso.')
      setForm({ full_name: '', birth_date: '', gender: '', phone: '', email: '' })
      loadPatients()
    } catch (err) {
      setMessage(err.message)
    }
  }

  const handleFieldChange = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  return (
    <div>
      <div className="topbar">
        <section className="page-header">
          <img className="page-icon-image" src="/static/assets/icons/novo-paciente.png" alt="Novo Paciente" />
          <div>
            <h1>Novo Paciente</h1>
          </div>
        </section>
      </div>
      <div className="form-card">
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <label>Nome completo</label>
            <input value={form.full_name} onChange={(event) => handleFieldChange('full_name', event.target.value)} required />
          </div>
          <div className="grid-two">
            <div className="form-row">
              <label>Data de nascimento</label>
              <input value={form.birth_date} onChange={(event) => handleFieldChange('birth_date', formatDateInput(event.target.value))} placeholder="dd/mm/aaaa" />
            </div>
            <div className="form-row">
              <label>Gênero</label>
              <select value={form.gender} onChange={(event) => handleFieldChange('gender', event.target.value)}>
                <option value="">Selecione</option>
                <option value="Feminino">Feminino</option>
                <option value="Masculino">Masculino</option>
                <option value="Outro">Outro</option>
              </select>
            </div>
          </div>
          <div className="grid-two">
            <div className="form-row">
              <label>Telefone</label>
              <input value={form.phone} onChange={(event) => handleFieldChange('phone', formatPhoneInput(event.target.value))} placeholder="(00) 00000-0000" />
            </div>
            <div className="form-row">
              <label>Email</label>
              <input type="email" value={form.email} onChange={(event) => handleFieldChange('email', event.target.value)} />
            </div>
          </div>
          <button type="submit" className="button">
            Cadastrar
          </button>
        </form>
      </div>
      {message && <p className={message.includes('sucesso') ? 'success' : 'message'}>{message}</p>}
      <div className="card wide-card" style={{ marginTop: 20 }}>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Idade</th>
                <th>Telefone</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {patients.map((patient) => (
                <tr key={patient.id}>
                  <td>{patient.full_name}</td>
                  <td>{patient.age || '-'}</td>
                  <td>{patient.phone || '-'}</td>
                  <td>
                    <button
                      type="button"
                      className="delete-patient-btn"
                      onClick={() => confirmDelete(patient)}
                    >
                      Excluir Paciente
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {deleteTarget && (
        <div className="delete-overlay" onClick={cancelDelete}>
          <div className="delete-modal" onClick={(event) => event.stopPropagation()}>
            <p>
              Deseja realmente excluir o paciente <strong>{deleteTarget.full_name}</strong>?
              Esta ação não pode ser desfeita.
            </p>
            <div className="delete-confirm-actions">
              <button type="button" className="button-secondary delete-cancel" onClick={cancelDelete}>
                Cancelar
              </button>
              <button type="button" className="delete-confirm-btn" onClick={handleDelete}>
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function AccountPage({ user, onProfileUpdated }) {
  const [form, setForm] = useState({ full_name: user.full_name || '', profession: user.profession || '', gender: user.gender || '' })
  const [message, setMessage] = useState('')

  const handleChange = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setMessage('')
    try {
      const response = await apiPatch('/api/account', form)
      if (response?.user) {
        onProfileUpdated(response.user)
      }
      setMessage('Perfil atualizado com sucesso.')
    } catch (err) {
      setMessage(err.message)
    }
  }

  return (
    <div>
      <div className="topbar">
        <section className="page-header">
          <img className="page-icon-image" src="/static/assets/icons/dados-da-conta.png" alt="Perfil" />
          <div>
            <h1>Perfil</h1>
          </div>
        </section>
      </div>
      <div className="form-card">
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <label>Nome completo</label>
            <input value={form.full_name} onChange={(event) => handleChange('full_name', event.target.value)} />
          </div>
          <div className="form-row">
            <label>Profissão</label>
            <input value={form.profession} onChange={(event) => handleChange('profession', event.target.value)} />
          </div>
          <div className="form-row">
            <label>Gênero</label>
            <select value={form.gender} onChange={(event) => handleChange('gender', event.target.value)}>
              <option value="">Selecione</option>
              <option value="Feminino">Feminino</option>
              <option value="Masculino">Masculino</option>
              <option value="Outro">Outro</option>
            </select>
          </div>
          <button type="submit" className="button">
            Atualizar perfil
          </button>
        </form>
        {message && <p className={message.includes('sucesso') ? 'success' : 'message'}>{message}</p>}
      </div>
    </div>
  )
}

function ChatGeminiPage() {
  const [messages, setMessages] = useState([
    { role: 'model', text: 'Olá! Como posso ajudar você hoje com seus relatórios ou dúvidas?' },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  const sendChat = async (event) => {
    event.preventDefault()
    if (!input.trim()) {
      return
    }
    const userMessage = { role: 'user', text: input }
    setMessages((current) => [...current, userMessage])
    setInput('')
    setSending(true)
    setError('')

    try {
      const response = await apiPost('/api/chat-gemini', {
        contents: [{ role: 'user', parts: [{ text: input }] }],
      })
      setMessages((current) => [...current, { role: 'model', text: response.text }])
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  return (
    <div>
      <div className="topbar">
        <section className="page-header">
          <img className="page-icon-image" src="/static/assets/icons/usuario_user.png" alt="Chat Gemini" />
          <div>
            <h1>Chat Gemini</h1>
          </div>
        </section>
      </div>
      <div className="chat-container">
        <div className="chat-history">
          {messages.map((message, index) => (
            <div key={index} className={`chat-bubble ${message.role}`}>
              {message.text}
            </div>
          ))}
        </div>
        <form className="chat-input-row" onSubmit={sendChat}>
          <textarea
            className="chat-input"
            rows="2"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Digite sua mensagem..."
            disabled={sending}
          />
          <button type="submit" className="button" disabled={sending}>
            Enviar
          </button>
        </form>
        {error && <p className="message">{error}</p>}
      </div>
    </div>
  )
}

export default App
