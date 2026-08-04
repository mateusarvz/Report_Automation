import express from 'express'
import path from 'path'
import { fileURLToPath } from 'url'
import { createProxyMiddleware } from 'http-proxy-middleware'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const app = express()
const port = process.env.PORT || 4173

const clientBuildPath = path.join(__dirname, 'dist')

app.use(express.json())
app.use(['/api', '/static'], createProxyMiddleware({
  target: 'http://127.0.0.1:8000',
  changeOrigin: true,
  secure: false,
}))
app.use(express.static(clientBuildPath))

app.get('*', (req, res) => {
  res.sendFile(path.join(clientBuildPath, 'index.html'))
})

app.listen(port, () => {
  console.log(`Frontend server running on http://localhost:${port}`)
})
