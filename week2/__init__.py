import os

from flask import Flask
from flask import render_template

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_envvar('LTR_APPLICATION_SETTINGS', silent=True)
        #ALL_CLICKS_LOC = os.environ.get("ALL_CLICKS_LOC", app.config['ALL_CLICKS_LOC'])
        #app.config["ALL_CLICKS_LOC"] = ALL_CLICKS_LOC
        #print(app.config)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # A simple landing page
    #@app.route('/')
    #def index():
    #    return render_template('index.jinja2')

    from . import search
    app.register_blueprint(search.bp)
    app.add_url_rule('/', view_func=search.query)

    return app
