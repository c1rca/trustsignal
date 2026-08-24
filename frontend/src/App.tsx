import { AuthGate } from './components/auth/AuthGate'
import { AppShell } from './components/layout/AppShell'
import { UploadDropzone } from './components/upload/UploadDropzone'

function App() {
  return (
    <AppShell>
      <AuthGate>
        <UploadDropzone />
      </AuthGate>
    </AppShell>
  )
}

export default App
