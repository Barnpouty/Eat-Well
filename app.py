from flask import Flask, render_template

app = Flask(__name__)

CHECKOUT_URL = "https://checkout.escalepay.com/8372485"


@app.context_processor
def inject_globals():
    return {"checkout_url": CHECKOUT_URL}


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
