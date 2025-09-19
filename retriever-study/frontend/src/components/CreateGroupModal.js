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
  const [department, setDepartment] = useState(defaultCourse ? defaultCourse.substring(0, 4).toUpperCase() : '');
  const [difficulty, setDifficulty] = useState('');
  const [meetingType, setMeetingType] = useState('');
  const [timeSlot, setTimeSlot] = useState('');
  const [studyStyles, setStudyStyles] = useState([]);
  const [groupSize, setGroupSize] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setCourseCode(defaultCourse);
      setDepartment(defaultCourse ? defaultCourse.substring(0, 4).toUpperCase() : '');
      setDifficulty('');
      setMeetingType('');
      setTimeSlot('');
      setStudyStyles([]);
      setGroupSize('');
    }
  }, [isOpen, defaultCourse]);

  const departmentOptions = ['CMSC', 'MATH', 'PHYS', 'CHEM', 'BIOL', 'STAT'];
  const difficultyOptions = ['Beginner', 'Intermediate', 'Advanced'];
  const meetingTypeOptions = ['In-person', 'Online', 'Hybrid'];
  const timeSlotOptions = ['Morning', 'Afternoon', 'Evening', 'Weekend'];
  const studyStyleOptions = ['Group Discussion', 'Silent Study', 'Practice Problems', 'Exam Prep'];
  const groupSizeOptions = ['Small (2-4)', 'Medium (5-8)', 'Large (9+)'];

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
        department: department || null,
        difficulty: difficulty || null,
        meetingType: meetingType || null,
        timeSlot: timeSlot || null,
        studyStyle: studyStyles,
        groupSize: groupSize || null,
      };
      await onCreated(payload);
      // Reset for next time
      setTitle('');
      setDescription('');
      setTags('');
      setLocation('TBD');
      setMaxMembers(8);
      setDepartment(defaultCourse ? defaultCourse.substring(0, 4).toUpperCase() : '');
      setDifficulty('');
      setMeetingType('');
      setTimeSlot('');
      setStudyStyles([]);
      setGroupSize('');
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
                  onChange={(e) => {
                    const value = e.target.value;
                    setCourseCode(value);
                    if (!department) {
                      setDepartment(value.substring(0, 4).toUpperCase());
                    }
                  }}
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

            <div className="form-row">
              <div className="form-group">
                <label>Department</label>
                <select value={department} onChange={(e) => setDepartment(e.target.value)}>
                  <option value="">Select department</option>
                  {departmentOptions.map(option => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Difficulty</label>
                <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                  <option value="">Select difficulty</option>
                  {difficultyOptions.map(option => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Meeting Type</label>
                <select value={meetingType} onChange={(e) => setMeetingType(e.target.value)}>
                  <option value="">Select meeting format</option>
                  {meetingTypeOptions.map(option => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Preferred Time</label>
                <select value={timeSlot} onChange={(e) => setTimeSlot(e.target.value)}>
                  <option value="">Select time</option>
                  {timeSlotOptions.map(option => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
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

            <div className="form-group">
              <label>Study Style</label>
              <div className="study-style-options">
                {studyStyleOptions.map(option => {
                  const selected = studyStyles.includes(option);
                  return (
                    <label key={option} className={`pill-option ${selected ? 'pill-selected' : ''}`}>
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => {
                          setStudyStyles(prev => (
                            prev.includes(option)
                              ? prev.filter(item => item !== option)
                              : [...prev, option]
                          ));
                        }}
                      />
                      <span>{option}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="form-group">
              <label>Group Size Goal</label>
              <select value={groupSize} onChange={(e) => setGroupSize(e.target.value)}>
                <option value="">Select size</option>
                {groupSizeOptions.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
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
