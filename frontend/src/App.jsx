import { useAudioCapture } from './hooks/useAudioCapture'
import MicButton from './components/MicButton'
import ResultCard from './components/ResultCard'

function App() {
  const { isListening, startListening, result } = useAudioCapture()

  return (
    <div style={{ textAlign: 'center', padding: '2rem' }}>
      <h1>Shazam</h1>
      <MicButton onClick={startListening} isListening={isListening} />
      <ResultCard result={result} />
    </div>
  )
}

export default App