import React, { useState, useEffect } from 'react';
import './CreateGroupModal.css';

// Lightweight modal to create a study group quickly
const CreateGroupModal = ({
  isOpen,
  onClose,
  onCreated,
  defaultCourse = 'CS101',
}) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [courseCode, setCourseCode] = useState(defaultCourse);
  const [location, setLocation] = useState('TBD');
  const [tags, setTags] = useState('');
  const [maxMembers, setMaxMembers] = useState(8);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setCourseCode(defaultCourse);
    }
  }, [isOpen, defaultCourse]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;
    setSubmitting(true);
    try {
      const payload = {
        courseCode: courseCode.trim(),
        title: title.trim(),
        description: description.trim(),
        tags: tags
          .split(',')
          .map(t => t.trim())
          .filter(Boolean),
        timePrefs: [],
        location: location.trim() || 'TBD',
        maxMembers: Number(maxMembers) || 8,
        semester: null,
      };
      await onCreated(payload);
      // Reset for next time
      setTitle('');
      setDescription('');
      setTags('');
      setLocation('TBD');
      setMaxMembers(8);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <div className="modal-header">
          <h3 className="modal-title">Create Study Group</h3>
          <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-row">
              <div className="form-group">
                <label>Course Code</label>
                <input
                  value={courseCode}
                  onChange={(e) => setCourseCode(e.target.value)}
                  placeholder="e.g., CS101"
                  required
                />
              </div>
              <div className="form-group">
                <label>Max Members</label>
                <input
                  type="number"
                  min={2}
                  max={50}
                  value={maxMembers}
                  onChange={(e) => setMaxMembers(e.target.value)}
                />
              </div>
            </div>

            <div className="form-group">
              <label>Title</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., CS101 Exam 1 Study Crew"
                required
              />
            </div>

            <div className="form-group">
              <label>Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Purpose, schedule, and expectations"
                required
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Location</label>
                <input
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="TBD / ILS Library / Online"
                />
              </div>
              <div className="form-group">
                <label>Tags (comma separated)</label>
                <input
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="algorithms, exam-prep, evenings"
                />
              </div>
            </div>
            <p className="helper-text">You’ll be added as the first member automatically.</p>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn" onClick={onClose} disabled={submitting}>Cancel</button>
            <button type="submit" className="btn primary" disabled={submitting || !title || !description}>
              {submitting ? 'Creating…' : 'Create Group'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CreateGroupModal;

