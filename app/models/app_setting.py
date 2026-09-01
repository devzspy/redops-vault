from app.extensions import db

INFRA_ENGAGEMENT = "engagement"
INFRA_STANDING = "standing"
INFRA_MODES = (INFRA_ENGAGEMENT, INFRA_STANDING)

SINGLETON_ID = 1


class AppSetting(db.Model):
    __tablename__ = "app_settings"

    id = db.Column(db.Integer, primary_key=True)
    infra_mode = db.Column(db.String(20), nullable=False, default=INFRA_STANDING)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=True)

    engagement = db.relationship("Engagement")

    @classmethod
    def get(cls):
        """Return the singleton settings row, creating it with defaults if absent."""
        setting = cls.query.get(SINGLETON_ID)
        if setting is None:
            setting = cls(id=SINGLETON_ID, infra_mode=INFRA_STANDING)
            db.session.add(setting)
            db.session.commit()
        return setting
