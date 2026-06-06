import { useRef, useState } from 'react'

export function useAudioCapture() {
    const [isListening, setIsListening] = useState(false)
    const [result, setResult] = useState(null)
    const mediaRecorderRef = useRef(null)
    const chunksRef = useRef([])

    async function startListening() {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        const mediaRecorder = new MediaRecorder(stream)
        mediaRecorderRef.current = mediaRecorder
        chunksRef.current = []

        mediaRecorder.ondataavailable = (e) => {
            chunksRef.current.push(e.data)
        }

        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' })
            const formData = new FormData()
            formData.append('file', audioBlob, 'recording.webm')

            const response = await fetch('http://localhost:5000/api/match', {
                method: 'POST',
                body: formData
            })

            const data = await response.json()
            setResult(data)
        }

        mediaRecorder.start()
        setIsListening(true)

        setTimeout(() => {
            mediaRecorder.stop()
            stream.getTracks().forEach(t => t.stop())
            setIsListening(false)
        }, 5000)
    }

    return { isListening, startListening, result }
}