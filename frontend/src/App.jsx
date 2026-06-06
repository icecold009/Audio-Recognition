import { useState } from 'react'
import MicButton from './components/MicButton'

function App() {
  const [isListening, setIsListening] = useState(false)

  function handleMicClick() {
    setIsListening(!isListening)
  }

  return (
    <div>
      <h1>Shazam</h1>
      <MicButton onClick={handleMicClick} isListening={isListening} />
    </div>
  )
}

export default App