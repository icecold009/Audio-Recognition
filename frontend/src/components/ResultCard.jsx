function ResultCard({ result }) {
    if (!result) return null

    if (result.status === 'error' || result.status === 'rate_limited') {
        return <p style={{ color: 'red' }}>{result.error}</p>
    }

    return (
        <div style={{ marginTop: '2rem', textAlign: 'center' }}>
            <h2>{result.title}</h2>
            <p>{result.artist}</p>
            {result.album && <p style={{ color: 'gray' }}>{result.album}</p>}
        </div>
    )
}

export default ResultCard